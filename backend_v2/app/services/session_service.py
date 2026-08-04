from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone

from ..config import CONFIG, LLM_CONFIG, ONBOARDING_CONFIG, ModelConfig, OnboardingConfig
from ..llm.rationale_parser import RationaleParser, build_rationale_parser
from .bayesian_value_model import GridBayesianValueModel
from .value_taxonomy import VALUE_IDS, exported_taxonomy, value_palette
from .calendar_feature_service import action_features
from .calendar_conflict_service import CalendarConflictError, find_conflicts, validate_interval
from .calendar_adjustment_service import compound_features, net_adjustments, CONFIG as ADJUSTMENT_CONFIG
from .calendar_service import CalendarProvider, DEFAULT_CALENDAR_PROVIDER, current_week_start
from .scenario_service import BANK, GENERATOR
from .event_value_mapper import map_calendar_event
from .profile_transition_service import compare_profiles
from .onboarding_protocol_service import PROTOCOL, next_core_question, progress
from .conversation_prior_service import build_conversation_prior
from .onboarding_evidence_service import mark_prior_inclusions, validate_grounded_evidence_candidate
from ..llm.onboarding_interviewer import DeterministicOnboardingInterviewer, GeminiOnboardingInterviewer
from ..llm.onboarding_evidence_extractor import DeterministicOnboardingEvidenceExtractor, GeminiOnboardingEvidenceExtractor, PROMPT_VERSION as EXTRACTOR_PROMPT
from ..llm.onboarding_evidence_reviewer import DeterministicOnboardingEvidenceReviewer, GeminiOnboardingEvidenceReviewer, PROMPT_VERSION as REVIEWER_PROMPT
from ..llm.onboarding_interviewer import PROMPT_VERSION as INTERVIEWER_PROMPT


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    def __init__(self, rationale_parser: RationaleParser | None = None, model_config: ModelConfig = CONFIG,
                 calendar_provider: CalendarProvider = DEFAULT_CALENDAR_PROVIDER,
                 onboarding_config: OnboardingConfig = ONBOARDING_CONFIG, interviewer=None, extractor=None, reviewer=None):
        self.sessions: dict[str, dict] = {}
        self.rationale_parser = rationale_parser or build_rationale_parser(LLM_CONFIG)
        self.model_config = model_config
        self.calendar_provider = calendar_provider
        self.onboarding_config = onboarding_config
        role_types = {"deterministic", "gemini"}
        if {LLM_CONFIG.onboarding_interviewer, LLM_CONFIG.onboarding_extractor, LLM_CONFIG.onboarding_reviewer} - role_types:
            raise ValueError("Onboarding roles must be 'gemini' or 'deterministic'")
        self.interviewer = interviewer or (GeminiOnboardingInterviewer(LLM_CONFIG) if LLM_CONFIG.onboarding_interviewer == "gemini" else DeterministicOnboardingInterviewer())
        self.onboarding_extractor = extractor or (GeminiOnboardingEvidenceExtractor(LLM_CONFIG) if LLM_CONFIG.onboarding_extractor == "gemini" else DeterministicOnboardingEvidenceExtractor())
        self.onboarding_reviewer = reviewer or (GeminiOnboardingEvidenceReviewer(LLM_CONFIG) if LLM_CONFIG.onboarding_reviewer == "gemini" else DeterministicOnboardingEvidenceReviewer())

    def create(self, participant_id: str) -> dict:
        sid = f"session_{uuid.uuid4().hex[:12]}"
        week_start = current_week_start()
        self.sessions[sid] = {
            "id": sid, "participant_id": participant_id, "version": 0,
            "model": GridBayesianValueModel(self.model_config), "week_start": week_start.isoformat(),
            "calendar": self.calendar_provider.create_calendar(sid, week_start), "created_at": now(),
            "profile_status": "uninitialized", "profile_source": "neutral_base", "profile_stage": "uninitialized",
            "initial_profile_version": None, "initial_profile_created_at": None,
            "prior_status": "neutral", "current_round": 0, "total_rounds": 15, "round_status": "onboarding",
            "onboarding_status": "not_started", "onboarding_required": self.onboarding_config.enabled,
            "onboarding_protocol_version": PROTOCOL["protocol_version"], "onboarding": None,
            "scenario_order": [x["scenario_id"] for x in BANK.scenarios], "active_scenario_id": None,
            "active_event": None, "completed_rounds": [], "awaiting_decision": False, "awaiting_rationale": False,
            "previews": [], "decisions": [], "rationales": [], "value_evidence": [], "evidence_ledger": [], "chat_history": [],
            "profile_interactions": [],
            "calendar_revision": 0, "calendar_actions": [], "calendar_action_attempts": [],
            "round_calendar_before": None, "round_calendar_adjustments": [],
        }
        if not self.onboarding_config.enabled:
            self._use_neutral(self.sessions[sid], "research_configuration_disabled")
        return self.state(sid)

    def get(self, sid: str) -> dict:
        if sid not in self.sessions:
            raise KeyError(sid)
        return self.sessions[sid]

    def _profile(self, s: dict, force: bool = False) -> list[dict]:
        if s["profile_status"] != "initialized" and not force:
            return []
        profile = copy.deepcopy(s["model"].summary())
        for value in profile:
            linked = [e for e in s["value_evidence"] if e["value_id"] == value["id"]]
            linked.sort(key=lambda evidence: (
                evidence.get("created_at", ""),
                evidence.get("round", 0),
                abs(evidence.get("posterior_delta", 0)),
            ), reverse=True)
            value["evidence"] = copy.deepcopy(linked)
            value["conversation_evidence"] = [e for e in linked if e["source_type"] == "conversation"]
            value["calendar_action_evidence"] = [e for e in linked if e["source_type"] == "calendar_action"]
        return profile

    def state(self, sid: str) -> dict:
        s = self.get(sid)
        conflicts = self._active_request_conflicts(s)
        safe_active_event = copy.deepcopy(s["active_event"]) if s["active_event"] and (s["awaiting_decision"] or s["awaiting_rationale"]) else None
        return {"session_id": sid, "profile_status": s["profile_status"], "profile_version": s["version"],
                "profile_source": s["profile_source"], "profile_stage": s["profile_stage"],
                "initial_profile_version": s["initial_profile_version"], "initial_profile_created_at": s["initial_profile_created_at"],
                "initial_profile_displayed": bool(s.get("onboarding") and s["onboarding"].get("initial_profile_displayed")),
                "prior_status": s["prior_status"], "onboarding_status": s["onboarding_status"],
                "onboarding_required": s["onboarding_required"], "onboarding_protocol_version": s["onboarding_protocol_version"],
                "onboarding_progress": progress(s["onboarding"]) if s["onboarding"] else None,
                "onboarding_question_id": s["onboarding"].get("current_question_id") if s["onboarding"] else None,
                "onboarding_assistant_message": next((turn["message"] for turn in reversed(s["onboarding"].get("turns", [])) if turn["role"] == "assistant"), None) if s["onboarding"] else None,
                "onboarding_turns": copy.deepcopy(s["onboarding"].get("turns", [])) if s["onboarding_status"] == "active" and s["onboarding"] else None,
                "can_start_round": s["onboarding_status"] in {"complete", "neutral_fallback"},
                "current_profile": self._profile(s), "calendar": s["calendar"], "week_start": s["week_start"],
                "current_round": s["current_round"], "total_rounds": 15, "round_status": s["round_status"],
                "active_scenario_id": s["active_scenario_id"], "active_event": safe_active_event,
                "completed_rounds": s["completed_rounds"],
                "awaiting_decision": s["awaiting_decision"], "awaiting_rationale": s["awaiting_rationale"],
                "calendar_revision": s["calendar_revision"], "active_request_conflicts": conflicts,
                "accept_available": not conflicts,
                "value_palette": value_palette(),
                "pending_decision_id": next((d["decision_id"] for d in reversed(s["decisions"]) if not d["rationale_submitted"]), None)}

    def start_onboarding(self, sid: str) -> dict:
        s = self.get(sid)
        if s["onboarding_status"] in {"complete", "neutral_fallback"}:
            return {**self._onboarding_response(s), "assistant_message": "Onboarding has already been completed."}
        if s["onboarding_status"] == "active": return self._onboarding_response(s)
        first = PROTOCOL["core_questions"][0]
        opened = now()
        s["onboarding_status"] = "active"; s["round_status"] = "onboarding"
        s["onboarding"] = {"onboarding_id": f"onboarding_{uuid.uuid4().hex[:12]}",
            "protocol_id": PROTOCOL["protocol_id"], "protocol_version": PROTOCOL["protocol_version"],
            "status": "active", "started_at": opened, "completed_at": None, "completion_reason": None,
            "turns": [{"turn_id": f"onboarding_turn_{uuid.uuid4().hex[:12]}", "role": "assistant",
                       "question_id": first["id"], "message": first["wording"], "created_at": opened}],
            "answered_question_ids": [], "skipped_question_ids": [], "followup_ids": [],
            "followup_question_ids": [], "current_question_id": first["id"], "awaiting_followup": False,
            "participant_turn_count": 0, "transcript_frozen_at": None, "last_error": None,
            "participant_saw_prior_information": False, "initial_profile_displayed": False,
            "initial_profile_displayed_at": None, "displayed_profile_version": None}
        return {**self._onboarding_response(s), "assistant_message": "Before we begin, I’ll ask a few questions about how you usually organize your time. There are no right answers, and you can skip any question.\n\n" + first["wording"]}

    def _onboarding_response(self, s: dict) -> dict:
        record = s["onboarding"]
        last_assistant = next((turn["message"] for turn in reversed(record.get("turns", [])) if turn["role"] == "assistant"), None) if record else None
        return {"onboarding_status": s["onboarding_status"], "onboarding_id": record.get("onboarding_id") if record else None,
            "prior_status": s["prior_status"], "onboarding_protocol_version": s["onboarding_protocol_version"],
            "question_id": record.get("current_question_id") if record else None,
            "progress": progress(record) if record else None,
            "assistant_message": last_assistant, "can_complete": self._can_complete(record),
            "can_start_round": s["onboarding_status"] in {"complete", "neutral_fallback"},
            "profile_status": s["profile_status"], "profile_source": s["profile_source"],
            "profile_stage": s["profile_stage"], "profile_version": s["version"],
            "initial_profile_version": s["initial_profile_version"],
            "initial_profile_created_at": s["initial_profile_created_at"],
            "initial_profile_displayed": bool(record and record.get("initial_profile_displayed")),
            "current_profile": self._profile(s)}

    @staticmethod
    def _can_complete(record: dict | None) -> bool:
        if not record or record.get("awaiting_followup") or record.get("current_question_id") is not None:
            return False
        all_ids = {item["id"] for item in PROTOCOL["core_questions"]}
        handled = set(record["answered_question_ids"]) | set(record["skipped_question_ids"])
        return handled == all_ids and len(record["answered_question_ids"]) >= PROTOCOL["minimum_answered_core_questions"]

    def onboarding_message(self, sid: str, message: str) -> dict:
        s = self.get(sid); record = s["onboarding"]
        if s["onboarding_status"] != "active" or not record: raise ValueError("Onboarding is not active")
        if record["current_question_id"] is None: raise ValueError("All onboarding questions are complete; finish onboarding or use the neutral model.")
        if message.strip().lower() in {"skip", "prefer not to answer"}:
            return self.skip_onboarding_question(sid, record["current_question_id"])
        if record["participant_turn_count"] >= min(PROTOCOL["maximum_participant_turns"], self.onboarding_config.maximum_turns):
            raise ValueError("The onboarding turn limit has been reached; complete onboarding or use the neutral model.")
        question_id = record["current_question_id"]
        participant = {"turn_id": f"onboarding_turn_{uuid.uuid4().hex[:12]}", "role": "participant",
                       "question_id": question_id, "message": message, "created_at": now(),
                       "is_followup_answer": record["awaiting_followup"]}
        record["turns"].append(participant); record["participant_turn_count"] += 1
        if record["awaiting_followup"]:
            record["awaiting_followup"] = False
            if question_id not in record["answered_question_ids"]: record["answered_question_ids"].append(question_id)
            interview = None
        else:
            if question_id not in record["answered_question_ids"]: record["answered_question_ids"].append(question_id)
            remaining = min(PROTOCOL["maximum_followups"], self.onboarding_config.maximum_followups) - len(record["followup_ids"])
            interview = self.interviewer.respond(message, question_id, remaining)
        if interview and interview.should_ask_followup and question_id not in record["followup_question_ids"]:
            followup = next(item for item in PROTOCOL["approved_followups"] if item["id"] == interview.selected_followup_id)
            record["followup_ids"].append(followup["id"]); record["followup_question_ids"].append(question_id)
            record["awaiting_followup"] = True; wording = f"{interview.acknowledgement} {followup['wording']}"
        else:
            next_question = next_core_question(record)
            record["current_question_id"] = next_question["id"] if next_question else None
            wording = ("Thank you. " + next_question["wording"]) if next_question else "Thank you. I’ll prepare the scheduling scenarios now."
        assistant = {"turn_id": f"onboarding_turn_{uuid.uuid4().hex[:12]}", "role": "assistant",
                     "question_id": record["current_question_id"] or question_id, "message": wording, "created_at": now()}
        record["turns"].append(assistant)
        return {**self._onboarding_response(s), "assistant_message": wording, "turn_id": participant["turn_id"]}

    def skip_onboarding_question(self, sid: str, question_id: str) -> dict:
        s = self.get(sid); record = s["onboarding"]
        if s["onboarding_status"] != "active" or not record or record["current_question_id"] != question_id:
            raise ValueError("That onboarding question is not currently active")
        if question_id not in record["skipped_question_ids"]: record["skipped_question_ids"].append(question_id)
        record["awaiting_followup"] = False
        next_question = next_core_question(record); record["current_question_id"] = next_question["id"] if next_question else None
        wording = ("No problem. " + next_question["wording"]) if next_question else "No problem. I’ll prepare the scheduling scenarios now."
        record["turns"].append({"turn_id": f"onboarding_turn_{uuid.uuid4().hex[:12]}", "role": "assistant",
            "question_id": record["current_question_id"], "message": wording, "created_at": now()})
        return {**self._onboarding_response(s), "assistant_message": wording}

    def complete_onboarding(self, sid: str) -> dict:
        s = self.get(sid); record = s["onboarding"]
        if s["onboarding_status"] in {"complete", "neutral_fallback"}: return self._onboarding_response(s)
        if s["onboarding_status"] != "active" or not record: raise ValueError("Onboarding is not active")
        if not self._can_complete(record):
            raise ValueError("All six core questions must be answered or skipped, with at least five answered and no follow-up pending.")
        record["transcript_frozen_at"] = now()
        s["onboarding_status"] = "extracting"; record["status"] = "extracting"
        participant_turns = [turn for turn in record["turns"] if turn["role"] == "participant"]
        original = s["model"].posterior_copy()
        try:
            extracted = self.onboarding_extractor.extract(participant_turns)
            reviewed = self.onboarding_reviewer.review(extracted.evidence, participant_turns)
            evidence = []
            for index, candidate in enumerate(extracted.evidence):
                validate_grounded_evidence_candidate(candidate, participant_turns)
                review = next(item for item in reviewed.reviews if item.candidate_index == index)
                evidence.append({"evidence_id": f"onboarding_evidence_{uuid.uuid4().hex[:12]}", **candidate.model_dump(),
                    "review_status": review.review_status, "review_reason": review.review_reason,
                    "alternative_explanations": list(dict.fromkeys(candidate.alternative_explanations + review.alternative_explanations)),
                    "extractor_provider": extracted.provider, "extractor_model": extracted.model,
                    "reviewer_provider": reviewed.provider, "reviewer_model": reviewed.model,
                    "reviewer_taxonomy_version": reviewed.taxonomy_version, "created_at": now()})
            mark_prior_inclusions(evidence)
            accepted = sum(item["review_status"] == "accepted" for item in evidence)
            included = sum(item["included_in_prior"] for item in evidence)
            if included < self.onboarding_config.min_accepted_evidence:
                s["model"].replace_posterior(original); return self._use_neutral(s, "insufficient_grounded_evidence")
            built = build_conversation_prior(s["model"], evidence, self.onboarding_config)
            before_summary = s["model"].summary()
            informed_model = s["model"].clone(); informed_model.replace_posterior(built["conversation_informed_prior"])
            informed_summary = informed_model.summary()
            s["model"].replace_posterior(built["conversation_informed_prior"])
            s["value_evidence"].extend({
                "evidence_id": item["evidence_id"], "value_id": item["value_id"],
                "source_type": "conversation", "source_phase": "onboarding",
                "exact_text": item["exact_quote"], "directness": item["directness"],
                "relation": item["relation"], "strength": item["strength"],
                "review_status": item["review_status"], "created_at": item["created_at"],
            } for item in evidence if item["review_status"] != "rejected")
            created_at = now()
            s["version"] += 1; s["prior_status"] = "conversation_informed"; s["profile_status"] = "initialized"
            s["profile_source"] = "onboarding_conversation"; s["profile_stage"] = "conversation_initial"
            s["initial_profile_version"] = s["version"]; s["initial_profile_created_at"] = created_at
            s["onboarding_status"] = "complete"; s["round_status"] = "ready"
            record.update(status="complete", completed_at=now(), completion_reason="protocol_complete",
                current_question_id=None,
                extractor_result=extracted.raw_output, reviewer_result=reviewed.raw_output, reviewed_evidence=evidence,
                total_extracted_evidence_count=len(extracted.evidence), total_reviewed_evidence_count=len(evidence),
                accepted_evidence_count=accepted, included_prior_evidence_count=included,
                aggregate_scores=built["aggregate_scores"], clipped_scores=built["clipped_scores"],
                centered_scores=built["centered_scores"], prior_parameters=built["prior_parameters"],
                base_prior_summary=before_summary, conversation_prior_summary=informed_summary,
                initial_profile_summary=self._profile(s), initial_profile_version=s["version"],
                initial_profile_created_at=created_at,
                base_prior_distribution=built["base_prior"].tolist(), evidence_posterior_distribution=built["evidence_posterior"].tolist(),
                conversation_prior_distribution=built["conversation_informed_prior"].tolist(),
                interviewer_provider=LLM_CONFIG.onboarding_interviewer,
                interviewer_model=LLM_CONFIG.model if LLM_CONFIG.onboarding_interviewer == "gemini" else "protocol-controller-v1",
                extractor_provider=extracted.provider, extractor_model=extracted.model,
                reviewer_provider=reviewed.provider, reviewer_model=reviewed.model,
                reviewer_taxonomy_version=reviewed.taxonomy_version,
                prompt_versions={"interviewer": INTERVIEWER_PROMPT, "extractor": EXTRACTOR_PROMPT, "reviewer": REVIEWER_PROMPT})
            return {**self._onboarding_response(s), "assistant_message": "Thanks. We can now begin the scheduling scenarios.",
                    "accepted_evidence_count": accepted, "included_prior_evidence_count": included,
                    "profile_status": s["profile_status"], "profile_source": s["profile_source"],
                    "profile_stage": s["profile_stage"], "initial_profile_version": s["initial_profile_version"],
                    "profile_version": s["version"], "current_profile": self._profile(s)}
        except Exception as exc:
            s["model"].replace_posterior(original); s["onboarding_status"] = "active"; record["status"] = "active"
            record["last_error"] = {"message": str(exc), "retryable": True, "timestamp": now()}
            raise

    def _use_neutral(self, s: dict, reason: str) -> dict:
        s["onboarding_status"] = "neutral_fallback"; s["prior_status"] = "neutral"; s["round_status"] = "ready"
        s["profile_status"] = "uninitialized"; s["profile_source"] = "neutral_base"; s["profile_stage"] = "uninitialized"
        if s.get("onboarding") is None:
            s["onboarding"] = {"onboarding_id": f"onboarding_{uuid.uuid4().hex[:12]}", "protocol_id": PROTOCOL["protocol_id"],
                "protocol_version": PROTOCOL["protocol_version"], "turns": [], "answered_question_ids": [],
                "skipped_question_ids": [], "followup_ids": [], "current_question_id": None,
                "participant_saw_prior_information": False, "initial_profile_displayed": False,
                "initial_profile_displayed_at": None, "displayed_profile_version": None}
        s["onboarding"].update(status="neutral_fallback", completed_at=now(), completion_reason=reason,
                               accepted_evidence_count=0, reviewed_evidence=[], current_question_id=None)
        return {**self._onboarding_response(s), "assistant_message": "No problem. We will continue with a neutral starting model."}

    def use_neutral_prior(self, sid: str) -> dict:
        s = self.get(sid)
        if s["onboarding_status"] == "complete": return self._onboarding_response(s)
        return self._use_neutral(s, "participant_selected_neutral_prior")

    def next_event(self, sid: str) -> dict:
        s = self.get(sid)
        if s["onboarding_status"] not in {"complete", "neutral_fallback"}:
            raise ValueError("Conversational onboarding must be completed or skipped before Round 1.")
        if s["awaiting_decision"] or s["awaiting_rationale"]:
            raise ValueError("The current round must be resolved before starting another")
        if s["current_round"] >= 15:
            s["round_status"] = "session_complete"
            return {"status": "session_complete", **self.state(sid)}
        round_number = s["current_round"] + 1
        scenario_id = s["scenario_order"][round_number - 1]
        event = GENERATOR.generate(BANK.get(scenario_id), s["calendar"], round_number, s["week_start"]).model_dump()
        s.update(current_round=round_number, active_scenario_id=scenario_id, active_event=event,
                 awaiting_decision=True, awaiting_rationale=False, round_status="awaiting_decision",
                 round_calendar_before=copy.deepcopy(s["calendar"]), round_calendar_adjustments=[])
        if s["profile_source"] == "onboarding_conversation":
            s["profile_stage"] = "calendar_updating"
        return {"status": "round_started", "round": round_number, "total_rounds": 15, "event": event,
                **self.state(sid)}

    @staticmethod
    def _active_request_conflicts(s: dict) -> list[dict]:
        event = s.get("active_event")
        if not event or not s.get("awaiting_decision"):
            return []
        return find_conflicts(s["calendar"], event["requested_start"], event["requested_end"])

    def _active(self, s: dict, event_id: str) -> tuple[dict, dict, dict]:
        event = s["active_event"]
        if not event or event["scenario_id"] != event_id:
            raise ValueError("Event is not active")
        spec = BANK.get(s["active_scenario_id"])
        return event, spec, {**event, "action_features": spec["action_features"], "calendar": s["calendar"]}

    def preview(self, sid: str, event_id: str, action: str, candidate: dict | None, display_state: str) -> dict:
        s = self.get(sid)
        if not s["awaiting_decision"]:
            raise ValueError("Session is not awaiting a decision")
        event, _, scenario = self._active(s, event_id)
        schedule = candidate if action == "reschedule" else ({"start": event["requested_start"], "end": event["requested_end"]} if action == "accept" else None)
        conflicts = find_conflicts(s["calendar"], schedule["start"], schedule["end"]) if schedule else []
        if conflicts:
            return {"feasible": False, "reason": "calendar_conflict", "conflicts": conflicts,
                    "calendar_revision": s["calendar_revision"], "event_id": event_id, "action": action,
                    "preview_transition": None}
        adjustments = net_adjustments(s["round_calendar_before"] or s["calendar"], s["calendar"])
        features = compound_features(action_features(scenario, candidate), action, adjustments)
        before = s["model"].summary()
        hypothetical = s["model"].clone()
        hypothetical.observe_action(action, features)
        preview_profile = hypothetical.summary()
        preview_timestamp = now()
        preview_id = f"preview_{uuid.uuid4().hex[:12]}"
        transition = compare_profiles(before, preview_profile, stage="preview", hypothetical=True,
            profile_version_before=s["version"], profile_version_after=None,
            display_allowed=s["profile_status"] == "initialized", action=action, round=s["current_round"],
            scenario_id=s["active_scenario_id"], preview_id=preview_id,
            calendar_revision=s["calendar_revision"], timestamp=preview_timestamp)
        record = {"preview_id": preview_id, "event_id": event_id,
                  "scenario_id": s["active_scenario_id"], "round": s["current_round"], "action": action,
                  "candidate_schedule": candidate, "preview_profile": preview_profile, "preview_transition": transition,
                  "display_timestamp": preview_timestamp,
                  "display_state": display_state, "preview_order": len(s["previews"]) + 1,
                  "viewing_duration_ms": None, "base_profile_version": s["version"],
                  "calendar_revision": s["calendar_revision"], "feasible": True, "calendar_adjustments": adjustments}
        record["cache_key"] = {"session_id": sid, "profile_version": s["version"], "calendar_revision": s["calendar_revision"],
                               "scenario_id": s["active_scenario_id"], "action": action, "candidate_schedule": candidate}
        s["previews"].append(record)
        return {**record, "current_profile": self._profile(s), "profile_status": s["profile_status"],
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}

    @staticmethod
    def _by_id(summary: list[dict]) -> dict[str, dict]:
        return {item["id"]: item for item in summary}

    def calendar_action(self, sid: str, action_type: str, event_id: str, new_schedule: dict | None,
                        changes: dict | None, source: str) -> dict:
        s = self.get(sid)
        if s["onboarding_status"] not in {"complete", "neutral_fallback"}:
            raise ValueError("Calendar editing is disabled during conversational onboarding")
        index = next((i for i, item in enumerate(s["calendar"]) if item["id"] == event_id), None)
        if index is None:
            raise ValueError("Calendar event not found")
        before = copy.deepcopy(s["calendar"][index])
        if before.get("temporary") or event_id == s.get("active_scenario_id"):
            raise ValueError("Temporary or active incoming events cannot be edited")
        after = copy.deepcopy(before)
        if action_type == "reschedule_existing":
            validate_interval(new_schedule["start"], new_schedule["end"])
            conflicts = find_conflicts(s["calendar"], new_schedule["start"], new_schedule["end"], event_id)
            if conflicts:
                s["calendar_action_attempts"].append({"action_type": action_type, "event_id": event_id, "conflicts": conflicts, "timestamp": now()})
                raise CalendarConflictError(conflicts)
            after.update(new_schedule)
        elif action_type == "modify_existing":
            unknown = set(changes or {}) - {"title"}
            if unknown or not str((changes or {}).get("title", "")).strip():
                raise ValueError("Only a non-empty title may be modified")
            after["title"] = changes["title"].strip()
        elif action_type != "remove_existing":
            raise ValueError("Unsupported calendar action")

        revision_before = s["calendar_revision"]
        if action_type == "remove_existing":
            s["calendar"].pop(index); final = None
        else:
            s["calendar"][index] = after; final = copy.deepcopy(after)
        s["calendar_revision"] += 1
        performed = "awaiting_decision" if s["awaiting_decision"] else "awaiting_rationale" if s["awaiting_rationale"] else "between_rounds"
        record = {"calendar_action_id": f"calendar_action_{uuid.uuid4().hex[:12]}", "action_type": action_type,
                  "event_id": event_id, "before": before, "after": final, "source": source,
                  "round": s["current_round"] if performed != "between_rounds" else None,
                  "scenario_id": s["active_scenario_id"] if performed != "between_rounds" else None,
                  "performed_while": performed, "timestamp": now(), "calendar_revision_before": revision_before,
                  "calendar_revision_after": s["calendar_revision"]}
        s["calendar_actions"].append(record); s["previews"].clear()
        return {**self.state(sid), "calendar_action": record}

    def _action_evidence(self, s: dict, decision: dict, event: dict, features: dict[str, list[float]],
                         before: list[dict], after: list[dict]) -> None:
        before_map, after_map = self._by_id(before), self._by_id(after)
        vector = features[decision["action"]]
        conflicts = find_conflicts(s["round_calendar_before"] or [], event["requested_start"], event["requested_end"])
        schedule_text = decision["candidate_schedule"] or {"start": event["requested_start"], "end": event["requested_end"]}
        adjustment_text = ", ".join(
            (f"Moved '{item['event_title']}' from {item['original_start']} to {item['final_start']}" if item["change_type"] == "rescheduled"
             else f"Removed '{item['event_title']}' scheduled at {item['original_start']}")
            for item in decision["round_calendar_adjustments"])
        exact = f"{adjustment_text + ', then ' if adjustment_text else ''}{decision['action'].capitalize()} '{event['title']}' at {schedule_text['start']}"
        for index, value_id in enumerate(VALUE_IDS):
            delta = after_map[value_id]["posterior_mean"] - before_map[value_id]["posterior_mean"]
            if vector[index] == 0 and abs(delta) < self.model_config.evidence_delta_threshold:
                continue
            record = {"evidence_id": f"evidence_{uuid.uuid4().hex[:12]}", "value_id": value_id,
                      "source_type": "calendar_action", "source_phase": "round", "round": decision["round"],
                      "scenario_id": decision["scenario_id"], "decision_id": decision["decision_id"], "exact_text": exact,
                      "action": decision["action"], "event_title": event["title"], "requested_schedule": {"start": event["requested_start"], "end": event["requested_end"]},
                      "candidate_schedule": decision["candidate_schedule"],
                      "affected_commitments": [{
                          "id": e["id"], "title": e["title"], "protected": e.get("protected", False),
                          "category": e.get("category"), "primary_value_id": e.get("primary_value_id"),
                          "value_mapping": e.get("value_mapping"),
                      } for e in conflicts],
                      "round_calendar_adjustments": decision["round_calendar_adjustments"], "compound_plan": decision["compound_plan"],
                      "event_value_mapping": event["value_mapping"],
                      "directness": None, "direction": "increase" if delta > 0 else "decrease" if delta < 0 else "negligible",
                      "posterior_before": before_map[value_id]["posterior_mean"], "posterior_after": after_map[value_id]["posterior_mean"],
                      "posterior_delta": round(delta, 6), "created_at": now()}
            s["value_evidence"].append(record)

    def decide(self, sid: str, event_id: str, action: str, candidate: dict | None) -> dict:
        s = self.get(sid)
        if not s["awaiting_decision"]:
            raise ValueError("Session is not awaiting a decision")
        event, _, scenario = self._active(s, event_id)
        schedule = candidate if action == "reschedule" else ({"start": event["requested_start"], "end": event["requested_end"]} if action == "accept" else None)
        conflicts = find_conflicts(s["calendar"], schedule["start"], schedule["end"]) if schedule else []
        if conflicts:
            raise CalendarConflictError(conflicts)
        adjustments = net_adjustments(s["round_calendar_before"] or s["calendar"], s["calendar"])
        features = compound_features(action_features(scenario, candidate), action, adjustments)
        version_before = s["version"]
        display_allowed = s["profile_status"] == "initialized"
        before = s["model"].summary(); s["model"].observe_action(action, features); after = s["model"].summary()
        if action in ("accept", "reschedule"):
            s["calendar"].append(map_calendar_event({
                "id": event_id, "title": event["title"], **schedule, "category": "incoming_request",
                "protected": False, "flexibility": "medium", "blocks_time": True,
                "event_value_id": event["event_value_id"],
            }))
        s["version"] += 1
        decision_id = f"decision_{uuid.uuid4().hex[:12]}"
        action_transition = compare_profiles(before, after, stage="action_commit", hypothetical=False,
            profile_version_before=version_before, profile_version_after=s["version"], display_allowed=display_allowed,
            action=action, round=s["current_round"], scenario_id=s["active_scenario_id"], decision_id=decision_id,
            calendar_revision=s["calendar_revision"], timestamp=now())
        decision = {"decision_id": decision_id, "event_id": event_id,
                    "scenario_id": s["active_scenario_id"], "round": s["current_round"], "action": action,
                    "candidate_schedule": candidate, "committed_at": now(), "profile_before": before,
                    "profile_after_action": after, "action_transition": action_transition,
                    "action_features": features, "rationale_submitted": False, "source_phase": "round",
                    "round_calendar_adjustments": adjustments,
                    "compound_plan": {"incoming_request_action": action, "incoming_request_schedule": schedule,
                                      "calendar_adjustments": adjustments, "final_calendar_outcome": copy.deepcopy(s["calendar"])}}
        s["round_calendar_adjustments"] = adjustments
        s["decisions"].append(decision); s["evidence_ledger"].append({"type": "calendar_action", **decision})
        self._action_evidence(s, decision, event, features, before, after)
        s["active_event"] = {**s["active_event"], "committedAction": action}
        s.update(awaiting_decision=False, awaiting_rationale=True, round_status="awaiting_rationale")
        return {**self.state(sid), "decision_id": decision["decision_id"], "ask_rationale": True,
                "prompt": "What mattered most to you in making that decision?", "action_transition": action_transition}

    def rationale(self, sid: str, decision_id: str, text: str) -> dict:
        s = self.get(sid)
        if not s["awaiting_rationale"]:
            raise ValueError("Session is not awaiting a rationale")
        decision = next((d for d in s["decisions"] if d["decision_id"] == decision_id), None)
        if not decision or decision["rationale_submitted"]:
            raise ValueError("Unknown or completed decision_id")
        parsed = self.rationale_parser.parse(text, {"action": decision["action"], "candidate_schedule": decision["candidate_schedule"],
                                                   "compound_plan": decision["compound_plan"],
                                                   "round_calendar_adjustments": decision["round_calendar_adjustments"]})
        version_before = s["version"]
        before = s["model"].summary()
        explicit, implicit = parsed.observation.explicit_value_references, parsed.observation.implicit_value_references
        s["model"].observe_values(explicit + implicit, self.model_config.rationale_reliability)
        after = s["model"].summary(); before_map, after_map = self._by_id(before), self._by_id(after)
        event_title = next((e["title"] for e in s["calendar"] if e["id"] == decision["event_id"]), s["active_event"]["title"])
        for value_id in dict.fromkeys(explicit + implicit):
            delta = after_map[value_id]["posterior_mean"] - before_map[value_id]["posterior_mean"]
            s["value_evidence"].append({"evidence_id": f"evidence_{uuid.uuid4().hex[:12]}", "value_id": value_id,
                "source_type": "conversation", "source_phase": "round", "round": decision["round"], "scenario_id": decision["scenario_id"],
                "decision_id": decision_id, "exact_text": text, "action": decision["action"], "event_title": event_title,
                "candidate_schedule": decision["candidate_schedule"], "directness": "explicit" if value_id in explicit else "implicit",
                "direction": "increase" if delta > 0 else "decrease" if delta < 0 else "negligible",
                "posterior_before": before_map[value_id]["posterior_mean"], "posterior_after": after_map[value_id]["posterior_mean"],
                "posterior_delta": round(delta, 6), "created_at": now()})
        s["version"] += 1; decision["rationale_submitted"] = True
        display_allowed = decision["action_transition"]["display_allowed"]
        rationale_transition = compare_profiles(before, after, stage="rationale", hypothetical=False,
            profile_version_before=version_before, profile_version_after=s["version"], display_allowed=display_allowed,
            action=decision["action"], round=decision["round"], scenario_id=decision["scenario_id"],
            decision_id=decision_id, calendar_revision=s["calendar_revision"], timestamp=now())
        round_transition = compare_profiles(decision["profile_before"], after, stage="round_complete", hypothetical=False,
            profile_version_before=decision["action_transition"]["profile_version_before"],
            profile_version_after=s["version"], display_allowed=display_allowed, action=decision["action"],
            round=decision["round"], scenario_id=decision["scenario_id"], decision_id=decision_id,
            calendar_revision=s["calendar_revision"], timestamp=now())
        record = {"decision_id": decision_id, "scenario_id": decision["scenario_id"], "round": decision["round"], "text": text,
                  "structured_observation": parsed.observation.model_dump(), "parser": {"provider": parsed.provider, "model": parsed.model},
                  "submitted_at": now(), "profile_before": before, "profile_after": after,
                  "rationale_transition": rationale_transition, "round_transition": round_transition, "source_phase": "round"}
        s["rationales"].append(record); s["evidence_ledger"].append({"type": "user_rationale", **record})
        s["profile_status"] = "initialized"
        if s["profile_stage"] == "uninitialized": s["profile_stage"] = "calendar_updating"
        s["completed_rounds"].append(s["current_round"])
        s.update(awaiting_rationale=False, round_status="complete", active_scenario_id=None, active_event=None)
        return {**self.state(sid), "structured_observation": parsed.observation.model_dump(),
                "assistant_message": f"Round {decision['round']} is complete. You can start the next round.",
                "rationale_transition": rationale_transition, "round_transition": round_transition}

    def chat(self, sid: str, message: str) -> dict:
        s = self.get(sid)
        if s["onboarding_status"] not in {"complete", "neutral_fallback"}:
            raise ValueError("Use the dedicated onboarding message endpoint during conversational onboarding")
        s["chat_history"].append({"role": "user", "text": message, "timestamp": now()})
        if s["awaiting_rationale"]:
            decision_id = next(d["decision_id"] for d in reversed(s["decisions"]) if not d["rationale_submitted"])
            result = self.rationale(sid, decision_id, message); reply = result["assistant_message"]
            s["chat_history"].append({"role": "assistant", "text": reply, "timestamp": now()})
            return {"text": reply, "rationale_recorded": True,
                    "rationale_transition": result["rationale_transition"], "round_transition": result["round_transition"],
                    **self.state(sid)}
        reply = "You can accept, decline, or choose another time. Previewing an option will not change your current profile." if s["awaiting_decision"] else "The round is complete. Start the next round when you are ready."
        s["chat_history"].append({"role": "assistant", "text": reply, "timestamp": now()})
        return {"text": reply, "rationale_recorded": False, **self.state(sid)}

    def initial_profile_viewed(self, sid: str, profile_version: int, displayed_at: str, source: str) -> dict:
        s = self.get(sid); record = s.get("onboarding")
        if s["onboarding_status"] != "complete" or s["profile_source"] != "onboarding_conversation" or not record:
            raise ValueError("A conversation-initial profile is not available")
        if profile_version != s["initial_profile_version"]:
            raise ValueError("Displayed profile version does not match the conversation-initial profile")
        if not record.get("initial_profile_displayed"):
            record.update(participant_saw_prior_information=True, initial_profile_displayed=True,
                          initial_profile_displayed_at=displayed_at, displayed_profile_version=profile_version,
                          initial_profile_display_source=source)
        return {"initial_profile_displayed": True, "displayed_profile_version": profile_version}

    def profile_interaction(self, sid: str, event_type: str, value_id: str, profile_version: int,
                            profile_stage: str, round_number: int, timestamp: str, source_phase: str) -> dict:
        s = self.get(sid)
        interaction = {"interaction_id": f"profile_interaction_{uuid.uuid4().hex[:12]}", "event_type": event_type,
                       "value_id": value_id, "profile_version": profile_version, "profile_stage": profile_stage,
                       "round": round_number, "timestamp": timestamp, "source_phase": source_phase}
        s["profile_interactions"].append(interaction)
        return copy.deepcopy(interaction)

    def export(self, sid: str) -> dict:
        s = self.get(sid)
        return {k: copy.deepcopy(v) for k, v in s.items() if k != "model"} | {
            "posterior_summary": s["model"].summary(), "value_dimensions": list(VALUE_IDS),
            "model_config": {**self.model_config.__dict__, "relative_weight_definition": "Posterior expected relative scheduling priority under the current model.",
                             "rationale_likelihood": "(1-r) + r * referenced_grid_priority / equal-share baseline",
                             "zero_boundary_approximation": "half a grid cell for alpha != 1"},
            "rationale_parser_config": {"provider": LLM_CONFIG.parser, "model": LLM_CONFIG.model},
            "scenario_generator_config": {"provider": LLM_CONFIG.scenario_generator, "model": LLM_CONFIG.model if LLM_CONFIG.scenario_generator == "gemini" else None},
            "action_feature_mappings": {x["scenario_id"]: x["action_features"] for x in BANK.scenarios},
            "calendar_adjustment_feature_config": ADJUSTMENT_CONFIG,
            "value_taxonomy": exported_taxonomy(), "value_palette": value_palette()}


sessions = SessionService()
