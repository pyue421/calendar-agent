import math
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import ModelConfig
from app.llm.rationale_parser import DeterministicRationaleParser
from app.main import app
from app.services.bayesian_value_model import GridBayesianValueModel, VALUE_IDS, simplex_grid
from app.services.scenario_service import BANK
from app.services.session_service import sessions
from scripts.prior_sensitivity import replay


client = TestClient(app)
TEST_CONFIG = ModelConfig(grid_step=0.1, prior_alpha=1.0, beta=5.0, rationale_reliability=0.65)


@pytest.fixture(autouse=True)
def deterministic_test_dependencies():
    original_parser, original_config = sessions.rationale_parser, sessions.model_config
    sessions.rationale_parser = DeterministicRationaleParser(); sessions.model_config = TEST_CONFIG
    yield
    sessions.rationale_parser = original_parser; sessions.model_config = original_config


def create_session():
    response = client.post("/api/sessions", json={"participant_id": "test"})
    assert response.status_code == 201
    return response.json()["session_id"], response.json()


def start(sid):
    response = client.post(f"/api/sessions/{sid}/events/next")
    assert response.status_code == 200
    return response.json()


def decide(sid, event, action="decline", candidate=None):
    response = client.post(f"/api/sessions/{sid}/decisions", json={"event_id": event["scenario_id"], "action": action, "candidate_schedule": candidate})
    assert response.status_code == 200
    return response.json()


def reflect(sid, text="Wellbeing and responsibility fairness mattered because I had made a promise."):
    response = client.post(f"/api/sessions/{sid}/chat", json={"message": text})
    assert response.status_code == 200 and response.json()["rationale_recorded"]
    return response.json()


def test_round_one_starts_uninitialized_without_calibration():
    sid, created = create_session()
    assert created["profile_status"] == "uninitialized" and created["current_profile"] == []
    assert created["current_round"] == 0 and created["round_status"] == "ready"
    assert len(created["calendar"]) == 10 and all(sid in event["id"] for event in created["calendar"])
    assert client.get(f"/api/sessions/{sid}/calibration").status_code == 404
    assert start(sid)["round"] == 1


def test_first_preview_and_action_stay_hidden_until_rationale():
    sid, _ = create_session(); event = start(sid)["event"]
    internal_before = sessions.get(sid)["model"].posterior.copy()
    preview = client.post(f"/api/sessions/{sid}/previews", json={"event_id": event["scenario_id"], "action": "accept", "display_state": "hover"}).json()
    assert preview["current_profile"] == [] and preview["profile_status"] == "uninitialized"
    assert len(preview["preview_profile"]) == 5
    assert np.array_equal(sessions.get(sid)["model"].posterior, internal_before)
    committed = decide(sid, event)
    assert committed["current_profile"] == [] and committed["profile_status"] == "uninitialized"
    completed = reflect(sid)
    assert completed["profile_status"] == "initialized" and len(completed["current_profile"]) == 5
    assert math.isclose(sum(x["relative_weight"] for x in completed["current_profile"]), 100, abs_tol=0.1)


def test_grid_prior_and_posterior_are_deterministic_normalized():
    first, second = simplex_grid(0.05), simplex_grid(0.05)
    assert first is second and first.shape[1] == 5
    assert np.allclose(first.sum(axis=1), 1) and np.all(first >= 0)
    model = GridBayesianValueModel(ModelConfig(grid_step=0.05, prior_alpha=1.0))
    assert np.allclose(model.posterior, model.posterior[0]) and math.isclose(float(model.posterior.sum()), 1)
    features = {"a": [0.5, 0, 0, 0, -0.5], "b": [-0.5, 0, 0, 0, 0.5]}
    model.observe_action("a", features)
    assert math.isclose(float(model.posterior.sum()), 1) and not np.allclose(model.posterior, model.posterior[0])
    assert not hasattr(model, "effective_sample_size") and not hasattr(model, "_resample")


def test_all_scenario_features_are_manual_five_dimensional_and_distinct():
    assert len(VALUE_IDS) == 5
    legacy = {"achievement", "reliability", "relationships", "autonomy", "collaboration", "fairness", "growth", "privacy", "community_contribution", "boundaries", "security"}
    for scenario in BANK.scenarios:
        assert scenario["feature_interpretation"]
        vectors = scenario["action_features"]
        assert set(vectors) == {"accept", "decline", "reschedule"}
        for vector in vectors.values():
            assert set(vector) == set(VALUE_IDS) and not (set(vector) & legacy)
            assert all(np.isfinite(value) and -1 <= value <= 1 for value in vector.values())
        assert vectors["accept"] != vectors["decline"]


def test_actions_and_candidate_times_have_distinct_non_mutating_previews():
    sid, _ = create_session(); event = start(sid)["event"]
    before = sessions.get(sid)["model"].posterior.copy()
    bodies = [
        {"event_id": event["scenario_id"], "action": "accept"},
        {"event_id": event["scenario_id"], "action": "decline"},
        {"event_id": event["scenario_id"], "action": "reschedule", "candidate_schedule": {"start": event["requested_start"], "end": event["requested_end"]}},
        {"event_id": event["scenario_id"], "action": "reschedule", "candidate_schedule": {"start": event["requested_start"][:11] + "20:00:00", "end": event["requested_start"][:11] + "21:00:00"}},
    ]
    profiles = [client.post(f"/api/sessions/{sid}/previews", json=body).json()["preview_profile"] for body in bodies]
    assert len({str(profile) for profile in profiles}) == 4
    assert np.array_equal(sessions.get(sid)["model"].posterior, before)


def test_exact_evidence_is_linked_and_preview_or_assistant_text_is_never_evidence():
    sid, _ = create_session(); event = start(sid)["event"]
    client.post(f"/api/sessions/{sid}/previews", json={"event_id": event["scenario_id"], "action": "accept"})
    decide(sid, event, "decline")
    quote = "Wellbeing mattered because I needed rest and responsibility fairness mattered because I promised my family."
    completed = reflect(sid, quote)
    evidence = sessions.export(sid)["value_evidence"]
    assert any(e["source_type"] == "calendar_action" and e["action"] == "decline" and e["event_title"] == event["title"] for e in evidence)
    assert any(e["source_type"] == "conversation" and e["exact_text"] == quote and e["directness"] == "explicit" for e in evidence)
    assert all(e["source_phase"] == "round" and e["posterior_before"] is not None and e["posterior_after"] is not None for e in evidence)
    assert not any("What mattered most" in e["exact_text"] for e in evidence)
    assert not any(e.get("source_type") == "preview" for e in evidence)
    profile = completed["current_profile"]
    assert any(value["conversation_evidence"] for value in profile) and any(value["calendar_action_evidence"] for value in profile)


def test_all_fifteen_rounds_and_export_configuration():
    sid, _ = create_session(); scenario_ids = []
    for _ in range(15):
        event = start(sid)["event"]; scenario_ids.append(event["scenario_id"])
        assert client.post(f"/api/sessions/{sid}/events/next").status_code == 400
        decide(sid, event); reflect(sid)
    finished = start(sid)
    assert finished["status"] == "session_complete" and len(set(scenario_ids)) == 15
    exported = client.get(f"/api/sessions/{sid}/export").json()
    assert len(exported["decisions"]) == len(exported["rationales"]) == 15
    assert exported["value_dimensions"] == list(VALUE_IDS)
    assert exported["model_config"]["prior_alpha"] == 1.0
    assert replay(exported, 2.0).shape == (5,)


def test_preview_performance_at_production_resolution():
    model = GridBayesianValueModel(ModelConfig(grid_step=0.025))
    started = time.perf_counter()
    model.observe_action("accept", {"accept": [0.2, 0.3, 0, -0.4, 0.5], "decline": [0.3, 0, 0.1, 0.5, -0.3], "reschedule": [0.2, 0.2, 0.1, 0.3, 0.3]})
    assert time.perf_counter() - started < 5.0
