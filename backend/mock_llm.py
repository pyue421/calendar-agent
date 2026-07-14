"""Canned responses for USE_MOCK_LLM mode.

Lets the DISCOVER pipeline run end-to-end with no API key — plumbing
tests only, not a stand-in for real inference quality. Each agent role
gets a fixed response shaped to match what agents/*.py expects to parse.
"""

from __future__ import annotations

import json

_JSON_RESPONSES = {
    "conflict_architect": {
        "emails": [
            {
                "sender": "Jordan Lee <jordan.lee@example.com>",
                "subject": "Quick sync tomorrow?",
                "body": (
                    "Hey! Could we grab 30 minutes tomorrow to go over the "
                    "roadmap doc before Thursday's review? Anytime works on "
                    "my end."
                ),
                "proposed_event": {
                    "title": "Roadmap Sync w/ Jordan",
                    "day_index": 1,
                    "start": "11:00",
                    "end": "11:30",
                    "category": "work",
                    "description": "Pre-review roadmap discussion",
                },
                "value_tensions": ["responsiveness vs. protected focus time"],
            }
        ],
        "intended_tensions": ["Helping a colleague vs. protecting deep work"],
        "difficulty": "easy",
        "targeting_rationale": "Mock scenario — no evidence yet, broad exploration probe.",
    },
    "advocate": {
        "arguments": [],
        "new_hypotheses": [
            {
                "label": "Protects focus time",
                "description": "Tends to keep deep-work blocks intact when possible.",
                "argument": "Mock advocate reasoning based on canned evidence.",
                "evidence": ["Mock evidence placeholder"],
                "initial_confidence": 0.5,
                "ladder": {
                    "raw_action": "Mock raw action",
                    "behavioral_pattern": "Mock pattern",
                    "scheduling_priority": "Mock priority",
                    "abstract_value": "Focus / deep work",
                },
            }
        ],
    },
    "challenger": {
        "challenges": [],
        "overarching_concerns": [
            "Mock mode: no real evidence has been gathered yet to challenge."
        ],
    },
    "synthesizer": {
        "synthesis_narrative": "Mock synthesis — no real debate occurred (mock LLM mode).",
        "hypothesis_updates": [],
    },
}

_TEXT_RESPONSES = {
    "scheduling_assistant": (
        "Thanks for letting me know! I've noted your preference. "
        "(This is a mock response — no real LLM call was made.)"
    ),
    "synthesizer": (
        "I noticed a scheduling choice come up this round — would you say "
        "that reflects how you usually prioritize things? "
        "(Mock reflection — no real LLM call was made.)"
    ),
}


def mock_response(role: str, expect_json: bool = False, round_num: int = 1) -> str:
    """Return a canned response for the given agent role.

    Args:
        role: agent role, e.g. "conflict_architect", "advocate".
        expect_json: whether the caller will json.loads() the result.
        round_num: current round number (unused for now, kept for parity
            with real providers so callers don't need branching logic).
    """
    if expect_json:
        data = _JSON_RESPONSES.get(role, {})
        return json.dumps(data)

    return _TEXT_RESPONSES.get(role, "Mock response (no real LLM call was made).")
