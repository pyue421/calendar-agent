"""Canned responses for USE_MOCK_LLM mode.

Lets the DISCOVER pipeline run end-to-end with no API key — plumbing
tests only, not a stand-in for real inference quality. Each agent role
gets a fixed response shaped to match what agents/*.py expects to parse.
"""

from __future__ import annotations

import json
import math

# Canned value hypotheses used to drive the mock synthesizer. All five are
# seeded up front (see seed_hypotheses / SessionManager.create_session) —
# the set is static. Every round only recomputes each one's confidence, so
# the ValuesPanel bubbles evolve their weight distribution without the
# labels or count ever changing.
_MOCK_HYPOTHESES = [
    {
        "label": "Wellbeing",
        "description": "Protects time for rest, health, and recovery.",
        "ladder": {
            "raw_action": "Kept a rest/workout block instead of an overlapping request",
            "behavioral_pattern": "Protects recovery time under pressure",
            "scheduling_priority": "Health over short-term convenience",
            "abstract_value": "Wellbeing",
        },
    },
    {
        "label": "Achievement & Growth",
        "description": "Leans into work that builds skills or moves key goals forward.",
        "ladder": {
            "raw_action": "Took on a stretch request that overlapped a free block",
            "behavioral_pattern": "Prioritizes forward-moving work over routine tasks",
            "scheduling_priority": "Growth opportunities over comfort",
            "abstract_value": "Achievement & Growth",
        },
    },
    {
        "label": "Relationships & Care",
        "description": "Makes room for colleagues, friends, or family.",
        "ladder": {
            "raw_action": "Accepted a request to connect with someone",
            "behavioral_pattern": "Says yes to social/relational asks",
            "scheduling_priority": "Relationship-building over strict efficiency",
            "abstract_value": "Relationships & Care",
        },
    },
    {
        "label": "Autonomy & Privacy",
        "description": "Protects control over their own time and boundaries.",
        "ladder": {
            "raw_action": "Declined a request that intruded on personal time",
            "behavioral_pattern": "Keeps personal blocks non-negotiable",
            "scheduling_priority": "Self-directed time over external asks",
            "abstract_value": "Autonomy & Privacy",
        },
    },
    {
        "label": "Value 5",
        "description": "Placeholder dimension — not yet named.",
        "ladder": {
            "raw_action": "Mock raw action",
            "behavioral_pattern": "Mock pattern",
            "scheduling_priority": "Mock priority",
            "abstract_value": "Value 5",
        },
    },
]


def _mock_confidence(round_num: int, index: int) -> float:
    """Deterministic, per-hypothesis confidence that drifts round to round."""
    phase = (round_num + index * 2) * 0.6
    value = 0.5 + 0.3 * math.sin(phase)
    return round(max(0.15, min(0.85, value)), 2)


def seed_hypotheses():
    """The five static ValueHypothesis objects a mock-mode session starts
    with (see SessionManager.create_session). Seeding them up front means
    the mock synthesizer never has to "add" a value mid-session — every
    round only ever adjusts confidence for this fixed set."""
    from models import ValueHypothesis

    return [
        ValueHypothesis(
            label=hyp["label"],
            description=hyp["description"],
            confidence=0.5,
            abstraction_ladder=hyp["ladder"],
        )
        for hyp in _MOCK_HYPOTHESES
    ]


def _mock_hypothesis_updates(round_num: int) -> list[dict]:
    """The five hypotheses are seeded at session creation (see
    seed_hypotheses) — every round only ever modifies their confidence
    (i.e. their share of the weight distribution). No round adds or
    removes a value."""
    updates = []
    for i, hyp in enumerate(_MOCK_HYPOTHESES):
        confidence = _mock_confidence(round_num, i)
        updates.append({
            "hypothesis_id": f"mock_{i}",
            "label": hyp["label"],
            "description": hyp["description"],
            "action": "modify",
            "new_confidence": confidence,
            "rationale": "Mock synthesis — no real debate occurred (mock LLM mode).",
            "new_evidence": [
                {
                    "description": f"Round {round_num} scheduling choice consistent with '{hyp['label']}'.",
                    "source_type": "behavioral",
                    "supports": True,
                    "strength": confidence,
                    "abstraction_level": "behavioral_pattern",
                }
            ],
            "ladder": hyp["ladder"],
        })
    return updates


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
    # "synthesizer" is handled dynamically in mock_response() — see
    # _mock_hypothesis_updates() — so the ledger evolves round over round
    # instead of staying permanently empty.
}

_TEXT_RESPONSES = {
    "scheduling_assistant": (
        "You've got a new request — Jordan asked about a quick roadmap sync "
        "tomorrow. It overlaps with your protected focus time. Take a look at "
        "the details below and let me know whether to accept or reject it. "
        "(Mock response — no real LLM call was made.)"
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
        round_num: current round number — the synthesizer response uses this
            to introduce/update value hypotheses so the ledger evolves round
            over round instead of staying permanently empty.
    """
    if expect_json:
        if role == "synthesizer":
            data = {
                "synthesis_narrative": (
                    f"Mock synthesis for round {round_num} — no real debate "
                    "occurred (mock LLM mode)."
                ),
                "hypothesis_updates": _mock_hypothesis_updates(round_num),
            }
        else:
            data = _JSON_RESPONSES.get(role, {})
        return json.dumps(data)

    return _TEXT_RESPONSES.get(role, "Mock response (no real LLM call was made).")
