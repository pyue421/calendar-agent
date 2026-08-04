import copy

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import ModelConfig
from app.llm.rationale_parser import DeterministicRationaleParser
from app.main import app
from app.services.event_value_mapper import event_value_mapping
from app.services.scenario_service import BANK, GENERATOR
from app.services.session_service import sessions
from app.services.value_taxonomy import VALUE_BY_ID, VALUE_DEFINITIONS, VALUE_IDS
from app.services.profile_transition_service import compare_profiles

client = TestClient(app)


@pytest.fixture(autouse=True)
def fast_model():
    parser, config = sessions.rationale_parser, sessions.model_config
    sessions.rationale_parser = DeterministicRationaleParser()
    sessions.model_config = ModelConfig(grid_step=.2)
    yield
    sessions.rationale_parser, sessions.model_config = parser, config


def active():
    created = client.post("/api/sessions", json={"participant_id": "mapping-test"}).json()
    sid = created["session_id"]
    client.post(f"/api/sessions/{sid}/onboarding/use-neutral-prior")
    started = client.post(f"/api/sessions/{sid}/events/next").json()
    return sid, created, started["event"]


def test_exactly_five_stable_value_definitions():
    assert len(VALUE_DEFINITIONS) == len(VALUE_IDS) == 5
    assert {item["id"]: (item["display_label"], item["full_label"], item["tone"]) for item in VALUE_DEFINITIONS} == {
        "wellbeing": ("Wellbeing", "Wellbeing", "green"),
        "achievement_growth": ("Achievement", "Achievement and Development", "rose"),
        "relationships_care": ("Relationships", "Relationships and Care", "amber"),
        "autonomy_privacy": ("Autonomy", "Autonomy and Privacy", "cyan"),
        "responsibility_fairness": ("Responsibility", "Responsibility and Fairness", "violet"),
    }
    assert all(item["taxonomy_version"] and item["definition"] and item["theoretical_notes"] for item in VALUE_DEFINITIONS)


def test_every_default_template_is_explicitly_mapped():
    assert sessions.calendar_provider.templates
    assert all(template.get("primary_value_id") in VALUE_BY_ID for template in sessions.calendar_provider.templates)


def test_all_scenarios_are_explicitly_mapped():
    assert len(BANK.scenarios) == 15
    assert all(scenario["event_value_id"] in VALUE_BY_ID for scenario in BANK.scenarios)


def test_generated_event_preserves_scenario_mapping():
    sid, created, _ = active()
    generated = GENERATOR.generate(BANK.get("s01"), copy.deepcopy(created["calendar"]), 1, created["week_start"]).model_dump()
    assert generated["event_value_id"] == "achievement_growth"
    assert generated["value_mapping"]["tone"] == "rose"
    assert "action_features" not in generated


def test_accept_and_reschedule_preserve_mapping():
    sid, _, event = active()
    state = sessions.get(sid)
    conflict = state["calendar"].index(next(item for item in state["calendar"] if item["id"] in event["conflicting_event_ids"]))
    state["calendar"].pop(conflict)
    accepted = client.post(f"/api/sessions/{sid}/decisions", json={"event_id": event["scenario_id"], "action": "accept"}).json()
    committed = next(item for item in accepted["calendar"] if item["id"] == event["scenario_id"])
    assert committed["primary_value_id"] == event["event_value_id"] and committed["value_mapping"] == event["value_mapping"]

    sid, _, event = active()
    day = event["requested_start"][:10]
    result = client.post(f"/api/sessions/{sid}/decisions", json={"event_id": event["scenario_id"], "action": "reschedule",
        "candidate_schedule": {"start": f"{day}T21:00:00", "end": f"{day}T22:00:00"}}).json()
    committed = next(item for item in result["calendar"] if item["id"] == event["scenario_id"])
    assert committed["primary_value_id"] == event["event_value_id"]


def test_calendar_edits_preserve_mapping():
    sid, created, _ = active()
    event = created["calendar"][0]
    day = event["start"][:10]
    moved = client.post(f"/api/sessions/{sid}/calendar-actions", json={"action_type": "reschedule_existing",
        "event_id": event["id"], "new_schedule": {"start": f"{day}T21:00:00", "end": f"{day}T22:00:00"},
        "source": "calendar_drag"}).json()
    moved_event = next(item for item in moved["calendar"] if item["id"] == event["id"])
    assert moved_event["value_mapping"] == event["value_mapping"]
    renamed = client.post(f"/api/sessions/{sid}/calendar-actions", json={"action_type": "modify_existing",
        "event_id": event["id"], "changes": {"title": "Renamed"}, "source": "calendar_event_modal"}).json()
    assert next(item for item in renamed["calendar"] if item["id"] == event["id"])["value_mapping"] == event["value_mapping"]


def test_unknown_event_is_neutral_and_mapping_is_inference_neutral():
    sid, _, _ = active()
    before = sessions.get(sid)["model"].posterior.copy()
    mapping = event_value_mapping({"title": "Imported event", "category": "unknown"})
    assert mapping["primary_value_id"] is None and mapping["tone"] == "neutral" and mapping["source"] == "unmapped"
    assert np.array_equal(before, sessions.get(sid)["model"].posterior)


def test_state_is_participant_safe_and_contains_palette():
    sid, created, event = active()
    assert all(item["value_mapping"]["tone"] in {"green", "rose", "amber", "cyan", "violet"} for item in created["calendar"])
    assert set(created["value_palette"]) == set(VALUE_IDS)
    assert "action_features" not in event
    assert "hidden_metadata" not in event
    assert "feature_interpretation" not in event


def test_profile_has_unified_evidence_with_source_types():
    sid, _, event = active()
    client.post(f"/api/sessions/{sid}/decisions", json={"event_id": event["scenario_id"], "action": "decline"})
    completed = client.post(f"/api/sessions/{sid}/chat", json={"message": "Wellbeing mattered because I needed rest."}).json()
    evidence = [item for value in completed["current_profile"] for item in value["evidence"]]
    assert evidence and {"conversation", "calendar_action"} <= {item["source_type"] for item in evidence}
    assert all("source_type" in item and "created_at" in item for item in evidence)


def test_export_contains_taxonomy_and_event_mappings():
    sid, _, _ = active()
    exported = client.get(f"/api/sessions/{sid}/export").json()
    assert len(exported["value_taxonomy"]) == 5
    assert exported["value_taxonomy"][1]["full_label"] == "Achievement and Development"
    assert exported["value_taxonomy"][1]["display_label"] == "Achievement"
    assert exported["value_palette"]["wellbeing"]["tone"] == "green"
    assert all("value_mapping" in event for event in exported["calendar"])


def transition_profile(weights):
    return [{"id": value_id, "posterior_mean": weight} for value_id, weight in zip(VALUE_IDS, weights)]


def test_profile_comparison_is_semantic_complete_and_precise():
    before = transition_profile([.2] * 5)
    after = transition_profile([.21, .19, .2, .2001, .1999])
    transition = compare_profiles(list(reversed(before)), after, stage="preview", hypothetical=True,
                                  profile_version_before=2)
    assert [item["value_id"] for item in transition["changes"]] == list(VALUE_IDS)
    assert len(transition["changes"]) == 5
    assert transition["changes"][0]["delta"] == pytest.approx(.01)
    assert transition["changes"][0]["delta_percentage_points"] == pytest.approx(1.0)
    assert transition["changes"][3]["direction"] == "negligible"


def test_profile_comparison_rejects_missing_duplicate_and_malformed_values():
    profile = transition_profile([.2] * 5)
    with pytest.raises(ValueError): compare_profiles(profile[:-1], profile, stage="preview", hypothetical=True, profile_version_before=0)
    with pytest.raises(ValueError): compare_profiles([*profile[:-1], profile[0]], profile, stage="preview", hypothetical=True, profile_version_before=0)
    malformed = copy.deepcopy(profile); malformed[0]["posterior_mean"] = float("nan")
    with pytest.raises(ValueError): compare_profiles(malformed, profile, stage="preview", hypothetical=True, profile_version_before=0)


def test_preview_and_committed_transitions_use_authoritative_profiles():
    sid, _, event = active()
    state = sessions.get(sid)
    posterior_before = state["model"].posterior.copy()
    preview = client.post(f"/api/sessions/{sid}/previews", json={"event_id": event["scenario_id"], "action": "decline", "display_state": "hover"}).json()
    assert preview["preview_transition"]["stage"] == "preview"
    assert preview["preview_transition"]["display_allowed"] is False
    assert preview["preview_transition"]["suppression_reason"] == "profile_not_initialized"
    preview_after = {item["id"]: item["posterior_mean"] for item in preview["preview_profile"]}
    assert all(change["after"] == preview_after[change["value_id"]] for change in preview["preview_transition"]["changes"])
    assert np.array_equal(posterior_before, state["model"].posterior)

    decision = client.post(f"/api/sessions/{sid}/decisions", json={"event_id": event["scenario_id"], "action": "decline"}).json()
    assert decision["action_transition"]["stage"] == "action_commit"
    assert decision["action_transition"]["display_allowed"] is False
    completed = client.post(f"/api/sessions/{sid}/chat", json={"message": "I needed time to rest."}).json()
    assert completed["rationale_transition"]["stage"] == "rationale"
    assert completed["round_transition"]["stage"] == "round_complete"
    assert completed["round_transition"]["display_allowed"] is False
    exported = client.get(f"/api/sessions/{sid}/export").json()
    assert exported["decisions"][0]["action_transition"]["changes"]
    assert exported["rationales"][0]["round_transition"]["changes"]
    assert "action_features" not in decision["action_transition"]
    second = client.post(f"/api/sessions/{sid}/events/next").json()["event"]
    second_preview = client.post(f"/api/sessions/{sid}/previews", json={"event_id": second["scenario_id"], "action": "decline", "display_state": "hover"}).json()
    assert second_preview["preview_transition"]["display_allowed"] is True
