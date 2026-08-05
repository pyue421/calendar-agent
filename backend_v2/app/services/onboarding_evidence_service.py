from __future__ import annotations

from ..models import OnboardingEvidenceCandidate

REVIEW_RANK = {"accepted": 2, "ambiguous": 1, "rejected": 0}
DIRECTNESS_RANK = {"explicit": 2, "implicit": 1, "ambiguous": 0}
STRENGTH_RANK = {"strong": 2, "moderate": 1, "weak": 0}


def validate_grounded_evidence_candidate(candidate: OnboardingEvidenceCandidate, participant_turns: list[dict]) -> dict:
    turn = next((item for item in participant_turns if item.get("turn_id") == candidate.turn_id), None)
    if not turn or turn.get("role") != "participant":
        raise ValueError("Onboarding evidence is not bound to a participant turn")
    if candidate.question_id != turn.get("question_id"):
        raise ValueError("Onboarding evidence question does not match its participant turn")
    if not candidate.exact_quote or candidate.exact_quote not in turn.get("message", ""):
        raise ValueError("Onboarding evidence quote is not an exact excerpt of its participant turn")
    return turn


def mark_prior_inclusions(records: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str], list[tuple[int, dict]]] = {}
    for index, record in enumerate(records):
        record["candidate_index"] = index
        record["included_in_prior"] = False
        record["prior_exclusion_reason"] = "reviewer_rejected" if record["review_status"] == "rejected" else None
        if record["review_status"] != "rejected":
            groups.setdefault((record["turn_id"], record["value_id"], record["relation"]), []).append((index, record))
    for candidates in groups.values():
        winner_index, winner = max(candidates, key=lambda pair: (
            REVIEW_RANK[pair[1]["review_status"]], DIRECTNESS_RANK[pair[1]["directness"]],
            STRENGTH_RANK[pair[1]["strength"]], -pair[0]))
        winner["included_in_prior"] = True
        for index, record in candidates:
            if index != winner_index:
                record["prior_exclusion_reason"] = "duplicate_turn_value_relation"
    return records
