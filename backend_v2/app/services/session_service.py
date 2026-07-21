from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone

from ..config import CONFIG, LLM_CONFIG
from ..llm.rationale_parser import RationaleParser, build_rationale_parser
from .bayesian_value_model import BayesianValueModel
from .calendar_feature_service import action_features
from .scenario_service import SCENARIO, participant_scenario


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    def __init__(self, rationale_parser: RationaleParser | None = None):
        self.sessions: dict[str, dict] = {}
        self.rationale_parser = rationale_parser or build_rationale_parser(LLM_CONFIG)

    def create(self, participant_id: str) -> dict:
        sid = f"session_{uuid.uuid4().hex[:12]}"
        model = BayesianValueModel(CONFIG)
        self.sessions[sid] = {
            "id": sid, "participant_id": participant_id, "version": 0, "model": model,
            "calendar": copy.deepcopy(SCENARIO["calendar"]), "event_loaded": False,
            "previews": [], "decisions": [], "rationales": [], "evidence_ledger": [],
            "created_at": now(),
        }
        return self.state(sid)

    def get(self, sid: str) -> dict:
        if sid not in self.sessions:
            raise KeyError(sid)
        return self.sessions[sid]

    def state(self, sid: str) -> dict:
        session = self.get(sid)
        return {"session_id": sid, "profile_version": session["version"],
                "current_profile": session["model"].summary(), "calendar": session["calendar"],
                "pending_rationale": next((d["decision_id"] for d in reversed(session["decisions"]) if not d["rationale_submitted"]), None)}

    def next_event(self, sid: str) -> dict:
        session = self.get(sid)
        session["event_loaded"] = True
        return {"event": participant_scenario(), "current_profile": session["model"].summary(), "profile_version": session["version"]}

    def preview(self, sid: str, action: str, candidate: dict | None, display_state: str) -> dict:
        session = self.get(sid)
        before_version = session["version"]
        hypothetical = session["model"].clone()
        hypothetical.observe_action(action, action_features(SCENARIO, candidate))
        pid = f"preview_{uuid.uuid4().hex[:12]}"
        record = {"preview_id": pid, "event_id": SCENARIO["id"], "action": action,
                  "candidate_schedule": candidate, "preview_profile": hypothetical.summary(),
                  "display_timestamp": now(), "display_state": display_state,
                  "preview_order": len(session["previews"]) + 1, "viewing_duration_ms": None,
                  "base_profile_version": before_version}
        session["previews"].append(record)
        return {**record, "current_profile": session["model"].summary(),
                "uncertainty": [{"id": v["id"], "uncertainty": v["uncertainty"]} for v in record["preview_profile"]],
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}

    def decide(self, sid: str, action: str, candidate: dict | None) -> dict:
        session = self.get(sid)
        before = session["model"].summary()
        session["model"].observe_action(action, action_features(SCENARIO, candidate))
        if action in ("accept", "reschedule"):
            schedule = candidate or {"start": SCENARIO["requested_start"], "end": SCENARIO["requested_end"]}
            session["calendar"].append({"id": SCENARIO["id"], "title": SCENARIO["title"], **schedule, "category": "work", "protected": False})
        session["version"] += 1
        decision = {"decision_id": f"decision_{uuid.uuid4().hex[:12]}", "event_id": SCENARIO["id"],
                    "action": action, "candidate_schedule": candidate, "committed_at": now(),
                    "profile_before": before, "profile_after_action": session["model"].summary(),
                    "rationale_submitted": False}
        session["decisions"].append(decision)
        session["evidence_ledger"].append({"type": "calendar_action", **decision})
        return {**self.state(sid), "decision_id": decision["decision_id"], "ask_rationale": True,
                "prompt": "What mattered most to you in making that scheduling decision?"}

    def rationale(self, sid: str, decision_id: str, text: str) -> dict:
        session = self.get(sid)
        decision = next((d for d in session["decisions"] if d["decision_id"] == decision_id), None)
        if not decision:
            raise ValueError("Unknown decision_id")
        if decision["rationale_submitted"]:
            raise ValueError("Rationale already submitted")
        parse_result = self.rationale_parser.parse(text, {
            "action": decision["action"], "candidate_schedule": decision["candidate_schedule"]
        })
        parsed = parse_result.observation
        before = session["model"].summary()
        values = parsed.explicit_value_references + parsed.implicit_value_references
        session["model"].observe_values(values, CONFIG.rationale_reliability)
        session["version"] += 1
        decision["rationale_submitted"] = True
        record = {"decision_id": decision_id, "text": text, "structured_observation": parsed.model_dump(),
                  "parser": {"provider": parse_result.provider, "model": parse_result.model},
                  "submitted_at": now(), "profile_before": before, "profile_after": session["model"].summary()}
        session["rationales"].append(record)
        session["evidence_ledger"].append({"type": "user_rationale", **record})
        return {**self.state(sid), "structured_observation": parsed.model_dump()}

    def export(self, sid: str) -> dict:
        session = self.get(sid)
        return {k: copy.deepcopy(v) for k, v in session.items() if k != "model"} | {
            "posterior_summary": session["model"].summary(),
            "model_config": CONFIG.__dict__,
            "rationale_parser_config": {"provider": LLM_CONFIG.parser, "model": LLM_CONFIG.model},
        }


sessions = SessionService()
