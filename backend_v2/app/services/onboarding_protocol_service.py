from __future__ import annotations

import json
from pathlib import Path

PROTOCOL_PATH = Path(__file__).parents[1] / "data" / "onboarding_protocol.json"


def load_protocol() -> dict:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    required = {"protocol_id", "protocol_version", "core_questions", "approved_followups",
                "maximum_participant_turns", "maximum_followups", "minimum_answered_core_questions"}
    if not required <= set(protocol): raise RuntimeError("Onboarding protocol is missing required fields")
    ids = [item["id"] for item in protocol["core_questions"]]
    if len(ids) != 6 or len(set(ids)) != 6: raise RuntimeError("Onboarding protocol must contain six unique core questions")
    if any(not item.get("wording") for item in protocol["core_questions"]): raise RuntimeError("Invalid onboarding question")
    return protocol


PROTOCOL = load_protocol()


def progress(record: dict) -> dict:
    return {"answered_core": len(record["answered_question_ids"]),
            "required_core": PROTOCOL["minimum_answered_core_questions"],
            "total_core": len(PROTOCOL["core_questions"]),
            "maximum_turns": PROTOCOL["maximum_participant_turns"]}


def next_core_question(record: dict) -> dict | None:
    handled = set(record["answered_question_ids"]) | set(record["skipped_question_ids"])
    return next((item for item in PROTOCOL["core_questions"] if item["id"] not in handled), None)
