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
    started = client.post(f"/api/sessions/{sid}/events/next").json()
    return sid, created, started["event"]


def test_exactly_five_stable_value_definitions():
    assert len(VALUE_DEFINITIONS) == len(VALUE_IDS) == 5
    assert {item["id"]: (item["label"], item["tone"]) for item in VALUE_DEFINITIONS} == {
        "wellbeing": ("Wellbeing", "green"),
        "achievement_growth": ("Achievement & Growth", "rose"),
        "relationships_care": ("Relationships & Care", "amber"),
        "autonomy_privacy": ("Autonomy & Privacy", "cyan"),
        "responsibility_fairness": ("Responsibility & Fairness", "violet"),
    }


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
    assert exported["value_palette"]["wellbeing"]["tone"] == "green"
    assert all("value_mapping" in event for event in exported["calendar"])
