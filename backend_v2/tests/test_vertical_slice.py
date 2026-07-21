import math

import pytest

from fastapi.testclient import TestClient

from app.config import LLMConfig, ModelConfig
from app.llm.rationale_parser import DeterministicRationaleParser, GeminiRationaleParser, gemini_compatible_schema
from app.main import app
from app.models import RationaleObservation
from app.services.bayesian_value_model import BayesianValueModel
from app.services.session_service import sessions


client = TestClient(app)


@pytest.fixture(autouse=True)
def offline_rationale_parser():
    original = sessions.rationale_parser
    sessions.rationale_parser = DeterministicRationaleParser()
    yield
    sessions.rationale_parser = original


def create_session():
    response = client.post("/api/sessions", json={"participant_id": "test"})
    assert response.status_code == 201
    return response.json()["session_id"]


def test_preview_is_counterfactual_and_profiles_are_separate():
    sid = create_session()
    before = client.get(f"/api/sessions/{sid}/state").json()
    preview = client.post(f"/api/sessions/{sid}/previews", json={"event_id": "event_123", "action": "accept"}).json()
    after = client.get(f"/api/sessions/{sid}/state").json()
    assert after == before
    assert preview["current_profile"] == before["current_profile"]
    assert preview["preview_profile"] != preview["current_profile"]


def test_actions_and_reschedule_times_have_distinct_posteriors():
    sid = create_session()
    profiles = []
    for body in [
        {"event_id": "event_123", "action": "accept"},
        {"event_id": "event_123", "action": "decline"},
        {"event_id": "event_123", "action": "reschedule", "candidate_schedule": {"start": "2026-07-23T11:00:00", "end": "2026-07-23T12:00:00"}},
        {"event_id": "event_123", "action": "reschedule", "candidate_schedule": {"start": "2026-07-22T19:00:00", "end": "2026-07-22T20:00:00"}},
    ]:
        profiles.append(client.post(f"/api/sessions/{sid}/previews", json=body).json()["preview_profile"])
    assert len({str(p) for p in profiles}) == 4


def test_weights_normalize_and_low_ess_resamples():
    model = BayesianValueModel(ModelConfig(particle_count=50, resample_ess_ratio=0.99, beta=40))
    model.observe_action("a", {"a": [1] + [0] * 11, "b": [0, 1] + [0] * 10})
    assert math.isclose(sum(model.state.weights), 1.0)
    assert model.state.weights == [1 / 50] * 50
    assert math.isclose(model.effective_sample_size(), 50)


def test_decision_rationale_export_and_hidden_metadata():
    sid = create_session()
    event = client.post(f"/api/sessions/{sid}/events/next").json()["event"]
    assert "experimental_metadata" not in event and "action_features" not in event
    before = client.get(f"/api/sessions/{sid}/state").json()
    decision = client.post(f"/api/sessions/{sid}/decisions", json={"event_id": "event_123", "action": "decline"}).json()
    assert decision["profile_version"] == before["profile_version"] + 1
    rationale = client.post(f"/api/sessions/{sid}/rationales", json={"decision_id": decision["decision_id"], "rationale": "I needed to protect my personal time and rest."})
    assert rationale.status_code == 200
    exported = client.get(f"/api/sessions/{sid}/export").json()
    assert exported["decisions"] and exported["rationales"]
    assert "posterior_summary" in exported and "model_config" in exported
    assert exported["evidence_ledger"][1]["type"] == "user_rationale"


def test_rationale_schema_validation():
    parsed = DeterministicRationaleParser().parse(
        "I value fairness and must keep my promise to my family.", {"action": "decline"}
    ).observation
    assert parsed.directness == "explicit"
    assert "fairness" in parsed.explicit_value_references
    assert parsed.model_dump()["constraints"]


def test_gemini_parser_uses_structured_schema_and_user_evidence(monkeypatch):
    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {"text": '{"explicit_value_references":["fairness"],"implicit_value_references":[],"protected_commitments":[],"compromised_commitments":[],"constraints":[],"alternative_explanations":[],"directness":"explicit"}'})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.models = FakeModels()

    monkeypatch.setattr("app.llm.rationale_parser.genai.Client", FakeClient)
    result = GeminiRationaleParser(LLMConfig(api_key="test-key", model="gemini-test")).parse(
        "Fairness mattered to me.", {"action": "decline", "candidate_schedule": None}
    )
    assert result.observation.explicit_value_references == ["fairness"]
    assert "Fairness mattered to me." in captured["contents"]
    schema = captured["config"].response_schema
    assert schema["properties"]["directness"]["enum"] == ["explicit", "implicit", "ambiguous"]
    assert "additionalProperties" not in schema


def test_gemini_schema_removes_unsupported_additional_properties_recursively():
    schema = gemini_compatible_schema({
        "type": "object", "additionalProperties": False,
        "properties": {"nested": {"type": "object", "additionalProperties": False}},
    })
    assert "additionalProperties" not in schema
    assert "additionalProperties" not in schema["properties"]["nested"]
    # The local model remains strict even though the transport schema is reduced.
    with pytest.raises(Exception):
        RationaleObservation.model_validate({
            "explicit_value_references": [], "implicit_value_references": [],
            "protected_commitments": [], "compromised_commitments": [], "constraints": [],
            "alternative_explanations": [], "directness": "ambiguous", "unexpected": True,
        })
