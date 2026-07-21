from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone

from ..config import CONFIG, LLM_CONFIG
from ..llm.rationale_parser import RationaleParser, build_rationale_parser
from .bayesian_value_model import BayesianValueModel
from .calendar_feature_service import action_features
from .calibration_service import CALIBRATION
from .scenario_service import BANK, GENERATOR


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    def __init__(self, rationale_parser: RationaleParser | None = None):
        self.sessions: dict[str, dict] = {}
        self.rationale_parser = rationale_parser or build_rationale_parser(LLM_CONFIG)

    def create(self, participant_id: str) -> dict:
        sid = f"session_{uuid.uuid4().hex[:12]}"
        self.sessions[sid] = {
            "id": sid, "participant_id": participant_id, "version": 0,
            "model": BayesianValueModel(CONFIG), "calendar": [], "created_at": now(),
            "current_round": 0, "total_rounds": 15, "round_status": "calibration",
            "scenario_order": [s["scenario_id"] for s in BANK.scenarios], "active_scenario_id": None,
            "active_event": None, "completed_rounds": [], "awaiting_decision": False,
            "awaiting_rationale": False, "calibration_complete": False,
            "calibration": [], "previews": [], "decisions": [], "rationales": [],
            "evidence_ledger": [], "chat_history": [],
        }
        return self.state(sid)

    def get(self, sid: str) -> dict:
        if sid not in self.sessions:
            raise KeyError(sid)
        return self.sessions[sid]

    def _visible_profile(self, session: dict) -> list[dict]:
        return session["model"].summary() if session["calibration_complete"] else []

    def state(self, sid: str) -> dict:
        s = self.get(sid)
        return {
            "session_id": sid, "profile_version": s["version"], "current_profile": self._visible_profile(s),
            "calendar": s["calendar"], "current_round": s["current_round"], "total_rounds": 15,
            "round_status": s["round_status"], "active_scenario_id": s["active_scenario_id"],
            "completed_rounds": s["completed_rounds"], "awaiting_decision": s["awaiting_decision"],
            "awaiting_rationale": s["awaiting_rationale"], "calibration_complete": s["calibration_complete"],
            "calibration_progress": len(s["calibration"]), "calibration_total": len(CALIBRATION.questions),
            "pending_decision_id": next((d["decision_id"] for d in reversed(s["decisions"]) if not d["rationale_submitted"]), None),
        }

    def calibration_questions(self, sid: str) -> dict:
        s = self.get(sid)
        return {"complete": s["calibration_complete"], "responses": len(s["calibration"]),
                "questions": CALIBRATION.participant_questions(), "current_profile": self._visible_profile(s)}

    def calibrate(self, sid: str, question_id: str, choice: str, rationale: str) -> dict:
        s = self.get(sid)
        if s["calibration_complete"]:
            raise ValueError("Calibration is already complete")
        if any(r["question_id"] == question_id for r in s["calibration"]):
            raise ValueError("Calibration question already answered")
        expected = CALIBRATION.questions[len(s["calibration"])]["question_id"]
        if question_id != expected:
            raise ValueError("Calibration questions must be answered in order")
        before = s["model"].summary()
        s["model"].observe_action(choice, CALIBRATION.features(question_id))
        parsed = self.rationale_parser.parse(rationale, {"action": f"calibration:{choice}", "candidate_schedule": None})
        values = parsed.observation.explicit_value_references + parsed.observation.implicit_value_references
        s["model"].observe_values(values, CONFIG.rationale_reliability)
        record = {"question_id": question_id, "choice": choice, "rationale": rationale,
                  "structured_observation": parsed.observation.model_dump(), "parser": {"provider": parsed.provider, "model": parsed.model},
                  "profile_before": before, "profile_after": s["model"].summary(), "source_phase": "baseline_calibration", "submitted_at": now()}
        s["calibration"].append(record)
        s["evidence_ledger"].append({"type": "calibration_response", **record})
        s["version"] += 1
        if len(s["calibration"]) == len(CALIBRATION.questions):
            s["calibration_complete"] = True
            s["round_status"] = "ready"
        return {**self.state(sid), "baseline_profile": self._visible_profile(s), "next_question_index": len(s["calibration"])}

    def next_event(self, sid: str) -> dict:
        s = self.get(sid)
        if not s["calibration_complete"]:
            raise ValueError("Baseline calibration must be completed before Round 1")
        if s["awaiting_decision"] or s["awaiting_rationale"]:
            raise ValueError("The current round must be resolved before starting another")
        if s["current_round"] >= s["total_rounds"]:
            s["round_status"] = "session_complete"
            return {"status": "session_complete", **self.state(sid)}
        round_number = s["current_round"] + 1
        scenario_id = s["scenario_order"][round_number - 1]
        spec = BANK.get(scenario_id)
        event = GENERATOR.generate(spec, s["calendar"], round_number).model_dump()
        s.update(current_round=round_number, active_scenario_id=scenario_id, active_event=event,
                 awaiting_decision=True, awaiting_rationale=False, round_status="awaiting_decision")
        return {"status": "round_started", "round": round_number, "total_rounds": 15,
                "event": event, "current_profile": self._visible_profile(s), "profile_version": s["version"]}

    def _active(self, s: dict, event_id: str) -> tuple[dict, dict]:
        event = s["active_event"]
        if not event or event["scenario_id"] != event_id:
            raise ValueError("Event is not active")
        spec = BANK.get(s["active_scenario_id"])
        scenario = {**event, "action_features": spec["action_features"], "calendar": s["calendar"]}
        return event, scenario

    def preview(self, sid: str, event_id: str, action: str, candidate: dict | None, display_state: str) -> dict:
        s = self.get(sid)
        if not s["awaiting_decision"]:
            raise ValueError("Session is not awaiting a decision")
        _, scenario = self._active(s, event_id)
        hypothetical = s["model"].clone()
        hypothetical.observe_action(action, action_features(scenario, candidate))
        record = {"preview_id": f"preview_{uuid.uuid4().hex[:12]}", "event_id": event_id,
                  "scenario_id": s["active_scenario_id"], "round": s["current_round"], "action": action,
                  "candidate_schedule": candidate, "preview_profile": hypothetical.summary(), "display_timestamp": now(),
                  "display_state": display_state, "preview_order": len(s["previews"]) + 1,
                  "viewing_duration_ms": None, "base_profile_version": s["version"]}
        s["previews"].append(record)
        return {**record, "current_profile": self._visible_profile(s),
                "uncertainty": [{"id": v["id"], "uncertainty": v["uncertainty"]} for v in record["preview_profile"]],
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}

    def decide(self, sid: str, event_id: str, action: str, candidate: dict | None) -> dict:
        s = self.get(sid)
        if not s["awaiting_decision"]:
            raise ValueError("Session is not awaiting a decision")
        event, scenario = self._active(s, event_id)
        before = s["model"].summary()
        s["model"].observe_action(action, action_features(scenario, candidate))
        if action in ("accept", "reschedule"):
            schedule = candidate or {"start": event["requested_start"], "end": event["requested_end"]}
            s["calendar"].append({"id": event_id, "title": event["title"], **schedule, "category": "work", "protected": False})
        s["version"] += 1
        decision = {"decision_id": f"decision_{uuid.uuid4().hex[:12]}", "event_id": event_id,
                    "scenario_id": s["active_scenario_id"], "round": s["current_round"], "action": action,
                    "candidate_schedule": candidate, "committed_at": now(), "profile_before": before,
                    "profile_after_action": s["model"].summary(), "rationale_submitted": False, "source_phase": "round"}
        s["decisions"].append(decision); s["evidence_ledger"].append({"type": "calendar_action", **decision})
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
        parsed = self.rationale_parser.parse(text, {"action": decision["action"], "candidate_schedule": decision["candidate_schedule"]})
        before = s["model"].summary()
        values = parsed.observation.explicit_value_references + parsed.observation.implicit_value_references
        s["model"].observe_values(values, CONFIG.rationale_reliability)
        s["version"] += 1; decision["rationale_submitted"] = True
        record = {"decision_id": decision_id, "scenario_id": decision["scenario_id"], "round": decision["round"],
                  "text": text, "structured_observation": parsed.observation.model_dump(),
                  "parser": {"provider": parsed.provider, "model": parsed.model}, "submitted_at": now(),
                  "profile_before": before, "profile_after": s["model"].summary(), "source_phase": "round"}
        s["rationales"].append(record); s["evidence_ledger"].append({"type": "user_rationale", **record})
        s["completed_rounds"].append(s["current_round"])
        s.update(awaiting_rationale=False, round_status="complete", active_scenario_id=None, active_event=None)
        return {**self.state(sid), "structured_observation": parsed.observation.model_dump(),
                "assistant_message": f"Round {decision['round']} is complete. You can start the next round."}

    def chat(self, sid: str, message: str) -> dict:
        s = self.get(sid)
        s["chat_history"].append({"role": "user", "text": message, "timestamp": now()})
        if s["awaiting_rationale"]:
            decision_id = next(d["decision_id"] for d in reversed(s["decisions"]) if not d["rationale_submitted"])
            result = self.rationale(sid, decision_id, message)
            reply = result["assistant_message"]
            s["chat_history"].append({"role": "assistant", "text": reply, "timestamp": now()})
            return {"text": reply, "rationale_recorded": True, **self.state(sid)}
        if s["awaiting_decision"]:
            reply = "You can accept, decline, or choose another time. Previewing an option will not change your current profile."
        elif not s["calibration_complete"]:
            reply = "Please complete the baseline scheduling questions first."
        else:
            reply = "The round is complete. Start the next round when you are ready."
        s["chat_history"].append({"role": "assistant", "text": reply, "timestamp": now()})
        return {"text": reply, "rationale_recorded": False, **self.state(sid)}

    def export(self, sid: str) -> dict:
        s = self.get(sid)
        return {k: copy.deepcopy(v) for k, v in s.items() if k != "model"} | {
            "posterior_summary": s["model"].summary(),
            "model_config": {**CONFIG.__dict__, "prior_specification": "symmetric normalized exponential draws"},
            "rationale_parser_config": {"provider": LLM_CONFIG.parser, "model": LLM_CONFIG.model},
            "scenario_generator_config": {"provider": LLM_CONFIG.scenario_generator, "model": LLM_CONFIG.model if LLM_CONFIG.scenario_generator == "gemini" else None},
            "action_feature_mappings": {x["scenario_id"]: x["action_features"] for x in BANK.scenarios},
        }


sessions = SessionService()
