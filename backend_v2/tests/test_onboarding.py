import copy

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import ModelConfig, OnboardingConfig
from app.main import app
from app.models import OnboardingEvidenceCandidate
from app.services.bayesian_value_model import GridBayesianValueModel
from app.services.conversation_prior_service import build_conversation_prior
from app.services.onboarding_protocol_service import PROTOCOL
from app.services.session_service import sessions

client = TestClient(app)


@pytest.fixture(autouse=True)
def fast_grid():
    original = sessions.model_config
    sessions.model_config = ModelConfig(grid_step=.2)
    yield
    sessions.model_config = original


def fresh():
    created = client.post("/api/sessions", json={"participant_id": "onboarding-test"}).json()
    return created["session_id"], created


def start(sid):
    return client.post(f"/api/sessions/{sid}/onboarding/start").json()


ANSWERS = [
    "My busy week includes work deadlines and enough time for rest and health.",
    "I protected family time when a work deadline competed with it.",
    "I keep personal time and focus blocks because they support my wellbeing.",
    "I consider promises to my team and whether the request is fair.",
    "A worthwhile week includes learning, development, friends, and rest.",
    "I worry about breaking a promise or losing private personal time.",
]


def answer_five(sid):
    start(sid)
    result = None
    for answer in ANSWERS[:5]: result = client.post(f"/api/sessions/{sid}/onboarding/messages", json={"message": answer}).json()
    return result


def test_new_session_requires_onboarding_before_round_one():
    sid, created = fresh()
    assert created["onboarding_status"] == "not_started" and created["round_status"] == "onboarding"
    response = client.post(f"/api/sessions/{sid}/events/next")
    assert response.status_code == 400 and "onboarding" in response.json()["detail"].lower()


def test_protocol_has_six_fixed_nonleading_core_questions():
    assert PROTOCOL["protocol_version"] == "1.0.0"
    assert [item["id"] for item in PROTOCOL["core_questions"]] == ["typical_week", "competing_commitments",
        "protected_commitments", "unexpected_requests", "successful_week", "rescheduling_concerns"]
    assert not any(value_id in " ".join(item["wording"].lower() for item in PROTOCOL["core_questions"])
                   for value_id in ("achievement_growth", "relationships_care", "autonomy_privacy", "responsibility_fairness"))


def test_start_progress_skip_and_followup_limits_are_audited():
    sid, _ = fresh(); opened = start(sid)
    assert opened["question_id"] == "typical_week" and opened["progress"]["answered_core"] == 0
    short = client.post(f"/api/sessions/{sid}/onboarding/messages", json={"message": "Work is busy."}).json()
    assert len(sessions.get(sid)["onboarding"]["followup_ids"]) == 1 and short["question_id"] == "typical_week"
    client.post(f"/api/sessions/{sid}/onboarding/messages", json={"message": "I need rest after deadlines because health matters."})
    current = sessions.get(sid)["onboarding"]["current_question_id"]
    client.post(f"/api/sessions/{sid}/onboarding/skip-question", json={"question_id": current})
    assert current in sessions.get(sid)["onboarding"]["skipped_question_ids"]
    assert len(sessions.get(sid)["onboarding"]["followup_ids"]) <= 2


def test_neutral_fallback_is_stable_and_permits_round_one():
    sid, _ = fresh(); start(sid)
    result = client.post(f"/api/sessions/{sid}/onboarding/use-neutral-prior").json()
    assert result["onboarding_status"] == "neutral_fallback" and result["prior_status"] == "neutral"
    assert "conversation_prior" not in result and client.post(f"/api/sessions/{sid}/events/next").status_code == 200


def test_deterministic_prior_scores_mixture_and_model_validation():
    model = GridBayesianValueModel(ModelConfig(grid_step=.2))
    evidence = [{"value_id": "wellbeing", "relation": "supports", "directness": "explicit", "strength": "strong", "review_status": "accepted"},
                {"value_id": "achievement_growth", "relation": "challenges", "directness": "implicit", "strength": "weak", "review_status": "rejected"}]
    config = OnboardingConfig(evidence_scale=.75, mixture_weight=.35, score_clip=1, min_accepted_evidence=1)
    built = build_conversation_prior(model, evidence, config)
    assert built["aggregate_scores"]["wellbeing"] == 1.5 and built["clipped_scores"]["wellbeing"] == 1
    assert sum(built["centered_scores"].values()) == pytest.approx(0)
    assert built["conversation_informed_prior"].sum() == pytest.approx(1)
    assert np.linalg.norm(built["conversation_informed_prior"] - built["base_prior"]) < np.linalg.norm(built["evidence_posterior"] - built["base_prior"])
    with pytest.raises(ValueError): model.replace_posterior(np.array([1, -1]))


def test_successful_completion_is_atomic_visible_and_idempotent():
    sid, _ = fresh(); answer_five(sid)
    state = sessions.get(sid); neutral = state["model"].posterior_copy(); version = state["version"]
    result = client.post(f"/api/sessions/{sid}/onboarding/complete").json()
    assert result["onboarding_status"] == "complete" and result["prior_status"] == "conversation_informed"
    assert "prior" not in result and result["can_start_round"]
    assert state["profile_status"] == "initialized" and len(result["current_profile"]) == 5
    assert state["version"] == version + 1
    assert all(item["conversation_evidence"] for item in result["current_profile"])
    assert not np.array_equal(neutral, state["model"].posterior)
    applied = state["model"].posterior_copy()
    repeated = client.post(f"/api/sessions/{sid}/onboarding/complete").json()
    assert repeated["onboarding_status"] == "complete" and np.array_equal(applied, state["model"].posterior)


def test_insufficient_grounded_evidence_uses_neutral_fallback():
    sid, _ = fresh(); start(sid)
    for _ in range(5): client.post(f"/api/sessions/{sid}/onboarding/messages", json={"message": "My schedule varies from week to week without a clear pattern."})
    result = client.post(f"/api/sessions/{sid}/onboarding/complete").json()
    assert result["onboarding_status"] == "neutral_fallback" and sessions.get(sid)["onboarding"]["reviewed_evidence"] == []


def test_export_contains_sensitive_provenance_but_completion_response_does_not():
    sid, _ = fresh(); answer_five(sid); client.post(f"/api/sessions/{sid}/onboarding/complete")
    exported = client.get(f"/api/sessions/{sid}/export").json()["onboarding"]
    assert exported["turns"] and exported["reviewed_evidence"] and exported["prompt_versions"]
    assert exported["conversation_prior_distribution"] and exported["participant_saw_prior_information"] is False


def test_unknown_evidence_value_id_is_rejected():
    with pytest.raises(ValueError):
        OnboardingEvidenceCandidate(turn_id="t", question_id="q", exact_quote="quote", value_id="personality",
            relation="supports", directness="implicit", strength="weak")


def test_interviewer_does_not_mutate_model():
    sid, _ = fresh(); start(sid); before = sessions.get(sid)["model"].posterior_copy()
    client.post(f"/api/sessions/{sid}/onboarding/messages", json={"message": "Work is busy."})
    assert np.array_equal(before, sessions.get(sid)["model"].posterior)


def test_completion_failure_is_retryable_and_does_not_partially_mutate():
    class FailingExtractor:
        def extract(self, participant_turns):
            del participant_turns
            raise RuntimeError("temporary extraction failure")
    sid, _ = fresh(); answer_five(sid)
    state = sessions.get(sid); before = state["model"].posterior_copy(); version = state["version"]
    original = sessions.onboarding_extractor; sessions.onboarding_extractor = FailingExtractor()
    try:
        with pytest.raises(RuntimeError, match="temporary extraction failure"):
            sessions.complete_onboarding(sid)
    finally:
        sessions.onboarding_extractor = original
    assert np.array_equal(before, state["model"].posterior) and state["version"] == version
    assert state["onboarding_status"] == "active" and state["onboarding"]["last_error"]["retryable"]
