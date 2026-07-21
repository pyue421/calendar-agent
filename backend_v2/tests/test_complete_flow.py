import math

import pytest
from fastapi.testclient import TestClient

from app.config import ModelConfig
from app.llm.rationale_parser import DeterministicRationaleParser, gemini_compatible_schema
from app.main import app
from app.models import RationaleObservation
from app.services.bayesian_value_model import BayesianValueModel
from app.services.calibration_service import CALIBRATION
from app.services.session_service import SessionService, sessions


client = TestClient(app)


@pytest.fixture(autouse=True)
def deterministic_parser():
    original = sessions.rationale_parser
    sessions.rationale_parser = DeterministicRationaleParser()
    yield
    sessions.rationale_parser = original


def create_session():
    response = client.post("/api/sessions", json={"participant_id": "test"})
    assert response.status_code == 201
    return response.json()["session_id"]


def calibrate(sid):
    questions = client.get(f"/api/sessions/{sid}/calibration").json()["questions"]
    for index, question in enumerate(questions):
        response = client.post(f"/api/sessions/{sid}/calibration/responses", json={
            "question_id": question["question_id"], "choice": "a" if index % 2 == 0 else "b",
            "rationale": "This protects my wellbeing and reliability.",
        })
        assert response.status_code == 200
    return response.json()


def complete_round(sid, action="decline", request_preview=False):
    started = client.post(f"/api/sessions/{sid}/events/next").json()
    event = started["event"]
    if request_preview:
        preview = client.post(f"/api/sessions/{sid}/previews", json={"event_id": event["scenario_id"], "action": "accept", "display_state": "pinned"})
        assert preview.status_code == 200
    decision = client.post(f"/api/sessions/{sid}/decisions", json={"event_id": event["scenario_id"], "action": action}).json()
    rationale = client.post(f"/api/sessions/{sid}/chat", json={"message": "I needed to protect my personal time and reliability."})
    assert rationale.status_code == 200 and rationale.json()["rationale_recorded"]
    return started, decision


def test_calibration_updates_neutral_prior_and_gates_round_one():
    sid = create_session()
    internal = sessions.get(sid)
    prior = internal["model"].summary()
    assert client.get(f"/api/sessions/{sid}/state").json()["current_profile"] == []
    blocked = client.post(f"/api/sessions/{sid}/events/next")
    assert blocked.status_code == 400
    result = calibrate(sid)
    assert result["calibration_complete"] is True
    assert result["baseline_profile"] != prior
    assert all(item["source_phase"] == "baseline_calibration" for item in sessions.export(sid)["calibration"])


def test_scenario_bank_serves_exactly_fifteen_unique_rounds_and_blocks_unresolved():
    sid = create_session(); calibrate(sid); scenario_ids = []
    for round_number in range(1, 16):
        started = client.post(f"/api/sessions/{sid}/events/next")
        assert started.status_code == 200 and started.json()["round"] == round_number
        event = started.json()["event"]
        scenario_ids.append(event["scenario_id"])
        assert "hidden_metadata" not in event and "action_features" not in event and "generator_instructions" not in event
        assert client.post(f"/api/sessions/{sid}/events/next").status_code == 400
        decision = client.post(f"/api/sessions/{sid}/decisions", json={"event_id": event["scenario_id"], "action": "decline"}).json()
        assert client.post(f"/api/sessions/{sid}/events/next").status_code == 400
        completed = client.post(f"/api/sessions/{sid}/rationales", json={"decision_id": decision["decision_id"], "rationale": "I protected my boundaries."})
        assert completed.status_code == 200 and completed.json()["round_status"] == "complete"
    assert len(set(scenario_ids)) == 15
    finished = client.post(f"/api/sessions/{sid}/events/next").json()
    assert finished["status"] == "session_complete" and finished["current_round"] == 15


def test_previews_are_separate_non_mutating_and_candidate_sensitive():
    sid = create_session(); calibrate(sid)
    event = client.post(f"/api/sessions/{sid}/events/next").json()["event"]
    before = client.get(f"/api/sessions/{sid}/state").json()
    bodies = [
        {"event_id": event["scenario_id"], "action": "accept", "display_state": "hover"},
        {"event_id": event["scenario_id"], "action": "decline", "display_state": "pinned"},
        {"event_id": event["scenario_id"], "action": "reschedule", "candidate_schedule": {"start": "2026-07-23T11:00:00", "end": "2026-07-23T12:00:00"}},
        {"event_id": event["scenario_id"], "action": "reschedule", "candidate_schedule": {"start": "2026-07-23T19:00:00", "end": "2026-07-23T20:00:00"}},
    ]
    profiles = [client.post(f"/api/sessions/{sid}/previews", json=body).json() for body in bodies]
    assert client.get(f"/api/sessions/{sid}/state").json() == before
    assert all(p["current_profile"] == before["current_profile"] and p["preview_profile"] != p["current_profile"] for p in profiles)
    assert profiles[2]["preview_profile"] != profiles[3]["preview_profile"]


def test_rationale_chat_completes_round_and_export_contains_full_protocol():
    sid = create_session(); calibrate(sid)
    for index in range(15): complete_round(sid, request_preview=index == 0)
    client.post(f"/api/sessions/{sid}/events/next")
    exported = client.get(f"/api/sessions/{sid}/export").json()
    assert len(exported["calibration"]) == 6
    assert len(exported["previews"]) == 1
    assert len(exported["completed_rounds"]) == len(exported["decisions"]) == len(exported["rationales"]) == 15
    assert "posterior_summary" in exported and "model_config" in exported and "action_feature_mappings" in exported
    assert exported["round_status"] == "session_complete"


def test_particle_normalization_resampling_and_schema_compatibility():
    model = BayesianValueModel(ModelConfig(particle_count=50, resample_ess_ratio=0.99, beta=40))
    model.observe_action("a", {"a": [1] + [0] * 11, "b": [0, 1] + [0] * 10})
    assert math.isclose(sum(model.state.weights), 1.0) and math.isclose(model.effective_sample_size(), 50)
    schema = gemini_compatible_schema(RationaleObservation.model_json_schema())
    assert "additionalProperties" not in schema
    assert len(CALIBRATION.questions) == 6
