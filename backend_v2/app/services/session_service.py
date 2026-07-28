from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone

from ..config import CONFIG, LLM_CONFIG, ModelConfig
from ..llm.rationale_parser import RationaleParser, build_rationale_parser
from .bayesian_value_model import GridBayesianValueModel, VALUE_IDS
from .calendar_feature_service import action_features
from .calendar_conflict_service import CalendarConflictError, find_conflicts, validate_interval
from .calendar_adjustment_service import compound_features, net_adjustments, CONFIG as ADJUSTMENT_CONFIG
from .calendar_service import CalendarProvider, DEFAULT_CALENDAR_PROVIDER, current_week_start
from .scenario_service import BANK, GENERATOR


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    def __init__(self, rationale_parser: RationaleParser | None = None, model_config: ModelConfig = CONFIG,
                 calendar_provider: CalendarProvider = DEFAULT_CALENDAR_PROVIDER):
        self.sessions: dict[str, dict] = {}
        self.rationale_parser = rationale_parser or build_rationale_parser(LLM_CONFIG)
        self.model_config = model_config
        self.calendar_provider = calendar_provider

    def create(self, participant_id: str) -> dict:
        sid = f"session_{uuid.uuid4().hex[:12]}"
        week_start = current_week_start()
        self.sessions[sid] = {
            "id": sid, "participant_id": participant_id, "version": 0,
            "model": GridBayesianValueModel(self.model_config), "week_start": week_start.isoformat(),
            "calendar": self.calendar_provider.create_calendar(sid, week_start), "created_at": now(),
            "profile_status": "uninitialized", "current_round": 0, "total_rounds": 15, "round_status": "ready",
            "scenario_order": [x["scenario_id"] for x in BANK.scenarios], "active_scenario_id": None,
            "active_event": None, "completed_rounds": [], "awaiting_decision": False, "awaiting_rationale": False,
            "previews": [], "decisions": [], "rationales": [], "value_evidence": [], "evidence_ledger": [], "chat_history": [],
            "calendar_revision": 0, "calendar_actions": [], "calendar_action_attempts": [],
            "round_calendar_before": None, "round_calendar_adjustments": [],
        }
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
            value["conversation_evidence"] = [e for e in linked if e["source_type"] == "conversation"]
            value["calendar_action_evidence"] = [e for e in linked if e["source_type"] == "calendar_action"]
        return profile

    def state(self, sid: str) -> dict:
        s = self.get(sid)
        conflicts = self._active_request_conflicts(s)
        return {"session_id": sid, "profile_status": s["profile_status"], "profile_version": s["version"],
                "current_profile": self._profile(s), "calendar": s["calendar"], "week_start": s["week_start"],
                "current_round": s["current_round"], "total_rounds": 15, "round_status": s["round_status"],
                "active_scenario_id": s["active_scenario_id"], "completed_rounds": s["completed_rounds"],
                "awaiting_decision": s["awaiting_decision"], "awaiting_rationale": s["awaiting_rationale"],
                "calendar_revision": s["calendar_revision"], "active_request_conflicts": conflicts,
                "accept_available": not conflicts,
                "pending_decision_id": next((d["decision_id"] for d in reversed(s["decisions"]) if not d["rationale_submitted"]), None)}

    def next_event(self, sid: str) -> dict:
        s = self.get(sid)
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
                    "calendar_revision": s["calendar_revision"], "event_id": event_id, "action": action}
        adjustments = net_adjustments(s["round_calendar_before"] or s["calendar"], s["calendar"])
        features = compound_features(action_features(scenario, candidate), action, adjustments)
        hypothetical = s["model"].clone()
        hypothetical.observe_action(action, features)
        record = {"preview_id": f"preview_{uuid.uuid4().hex[:12]}", "event_id": event_id,
                  "scenario_id": s["active_scenario_id"], "round": s["current_round"], "action": action,
                  "candidate_schedule": candidate, "preview_profile": hypothetical.summary(), "display_timestamp": now(),
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
                      "candidate_schedule": decision["candidate_schedule"], "affected_commitments": [{"id": e["id"], "title": e["title"], "protected": e.get("protected", False), "category": e.get("category")} for e in conflicts],
                      "round_calendar_adjustments": decision["round_calendar_adjustments"], "compound_plan": decision["compound_plan"],
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
        before = s["model"].summary(); s["model"].observe_action(action, features); after = s["model"].summary()
        if action in ("accept", "reschedule"):
            s["calendar"].append({"id": event_id, "title": event["title"], **schedule, "category": "work", "protected": False, "flexibility": "medium", "blocks_time": True})
        s["version"] += 1
        decision = {"decision_id": f"decision_{uuid.uuid4().hex[:12]}", "event_id": event_id,
                    "scenario_id": s["active_scenario_id"], "round": s["current_round"], "action": action,
                    "candidate_schedule": candidate, "committed_at": now(), "profile_before": before,
                    "profile_after_action": after, "action_features": features, "rationale_submitted": False, "source_phase": "round",
                    "round_calendar_adjustments": adjustments,
                    "compound_plan": {"incoming_request_action": action, "incoming_request_schedule": schedule,
                                      "calendar_adjustments": adjustments, "final_calendar_outcome": copy.deepcopy(s["calendar"])}}
        s["round_calendar_adjustments"] = adjustments
        s["decisions"].append(decision); s["evidence_ledger"].append({"type": "calendar_action", **decision})
        self._action_evidence(s, decision, event, features, before, after)
        s.update(awaiting_decision=False, awaiting_rationale=True, round_status="awaiting_rationale")
        return {**self.state(sid), "decision_id": decision["decision_id"], "ask_rationale": True,
                "prompt": "What mattered most to you in making that decision?"}

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
        record = {"decision_id": decision_id, "scenario_id": decision["scenario_id"], "round": decision["round"], "text": text,
                  "structured_observation": parsed.observation.model_dump(), "parser": {"provider": parsed.provider, "model": parsed.model},
                  "submitted_at": now(), "profile_before": before, "profile_after": after, "source_phase": "round"}
        s["rationales"].append(record); s["evidence_ledger"].append({"type": "user_rationale", **record})
        s["profile_status"] = "initialized"; s["completed_rounds"].append(s["current_round"])
        s.update(awaiting_rationale=False, round_status="complete", active_scenario_id=None, active_event=None)
        return {**self.state(sid), "structured_observation": parsed.observation.model_dump(),
                "assistant_message": f"Round {decision['round']} is complete. You can start the next round."}

    def chat(self, sid: str, message: str) -> dict:
        s = self.get(sid); s["chat_history"].append({"role": "user", "text": message, "timestamp": now()})
        if s["awaiting_rationale"]:
            decision_id = next(d["decision_id"] for d in reversed(s["decisions"]) if not d["rationale_submitted"])
            result = self.rationale(sid, decision_id, message); reply = result["assistant_message"]
            s["chat_history"].append({"role": "assistant", "text": reply, "timestamp": now()})
            return {"text": reply, "rationale_recorded": True, **self.state(sid)}
        reply = "You can accept, decline, or choose another time. Previewing an option will not change your current profile." if s["awaiting_decision"] else "The round is complete. Start the next round when you are ready."
        s["chat_history"].append({"role": "assistant", "text": reply, "timestamp": now()})
        return {"text": reply, "rationale_recorded": False, **self.state(sid)}

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
            "calendar_adjustment_feature_config": ADJUSTMENT_CONFIG}


sessions = SessionService()
