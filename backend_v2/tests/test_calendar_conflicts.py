import copy

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import ModelConfig
from app.llm.rationale_parser import DeterministicRationaleParser
from app.main import app
from app.services.calendar_conflict_service import find_conflicts
from app.services.session_service import sessions

client = TestClient(app)


@pytest.fixture(autouse=True)
def fast_model():
    old_parser, old_config = sessions.rationale_parser, sessions.model_config
    sessions.rationale_parser = DeterministicRationaleParser()
    sessions.model_config = ModelConfig(grid_step=.2, prior_alpha=1, beta=5, rationale_reliability=.65)
    yield
    sessions.rationale_parser, sessions.model_config = old_parser, old_config


def active():
    created = client.post("/api/sessions", json={"participant_id": "conflict-test"}).json()
    sid = created["session_id"]
    started = client.post(f"/api/sessions/{sid}/events/next").json()
    return sid, started["event"], started


def move_conflict(sid, event, start_hour=21):
    state = client.get(f"/api/sessions/{sid}/state").json()
    conflict = state["active_request_conflicts"][0]
    day = event["requested_start"][:10]
    response = client.post(f"/api/sessions/{sid}/calendar-actions", json={"action_type": "reschedule_existing",
        "event_id": conflict["id"], "new_schedule": {"start": f"{day}T{start_hour}:00:00", "end": f"{day}T{start_hour + 1}:00:00"}, "source": "calendar_drag"})
    assert response.status_code == 200
    return conflict, response.json()


def decision(sid, event, action="accept", candidate=None):
    return client.post(f"/api/sessions/{sid}/decisions", json={"event_id": event["scenario_id"], "action": action, "candidate_schedule": candidate})


def test_01_new_session_revision_zero():
    sid, _, _ = active(); assert sessions.get(sid)["calendar_revision"] == 0


def test_02_accept_unavailable_for_requested_conflict():
    _, _, state = active(); assert not state["accept_available"] and state["active_request_conflicts"]


def test_03_conflicting_accept_returns_structured_409():
    sid, event, _ = active(); response = decision(sid, event); assert response.status_code == 409 and response.json()["detail"]["code"] == "calendar_conflict"


def test_04_rejected_accept_is_transactional():
    sid, event, _ = active(); s = sessions.get(sid); before = (s["model"].posterior.copy(), copy.deepcopy(s["calendar"]), copy.deepcopy(s["value_evidence"]), s["round_status"], s["version"])
    decision(sid, event); assert np.array_equal(s["model"].posterior, before[0]) and (s["calendar"], s["value_evidence"], s["round_status"], s["version"]) == before[1:]


def test_05_move_conflict_enables_accept():
    sid, event, _ = active(); _, result = move_conflict(sid, event); assert result["accept_available"] and not result["active_request_conflicts"]


def test_06_accept_after_move_commits():
    sid, event, _ = active(); move_conflict(sid, event); assert decision(sid, event).status_code == 200


def test_07_reschedule_rejects_conflict():
    sid, event, _ = active(); candidate = {"start": event["requested_start"], "end": event["requested_end"]}; assert decision(sid, event, "reschedule", candidate).status_code == 409


def test_08_reschedule_accepts_free_candidate():
    sid, event, _ = active(); day = event["requested_start"][:10]; candidate = {"start": f"{day}T21:00:00", "end": f"{day}T22:00:00"}; assert decision(sid, event, "reschedule", candidate).status_code == 200


def test_09_adjacent_boundaries_are_available():
    calendar = [{"id": "a", "title": "A", "start": "2026-01-01T10:00:00", "end": "2026-01-01T11:00:00"}]; assert find_conflicts(calendar, "2026-01-01T11:00:00", "2026-01-01T12:00:00") == []


def test_10_reschedule_excludes_self():
    sid, _, _ = active(); event = sessions.get(sid)["calendar"][0]; body = {"action_type": "reschedule_existing", "event_id": event["id"], "new_schedule": {"start": event["start"], "end": event["end"]}, "source": "calendar_drag"}; assert client.post(f"/api/sessions/{sid}/calendar-actions", json=body).status_code == 200


def test_11_existing_move_onto_event_rejected():
    sid, _, _ = active(); first, second = sessions.get(sid)["calendar"][:2]; body = {"action_type": "reschedule_existing", "event_id": first["id"], "new_schedule": {"start": second["start"], "end": second["end"]}, "source": "calendar_drag"}; assert client.post(f"/api/sessions/{sid}/calendar-actions", json=body).status_code == 409


def test_12_failed_calendar_edit_unchanged():
    sid, _, _ = active(); s = sessions.get(sid); before = copy.deepcopy(s["calendar"]); first, second = before[:2]; client.post(f"/api/sessions/{sid}/calendar-actions", json={"action_type": "reschedule_existing", "event_id": first["id"], "new_schedule": {"start": second["start"], "end": second["end"]}, "source": "calendar_drag"}); assert s["calendar"] == before and s["calendar_revision"] == 0


def test_13_successful_edit_increments_revision():
    sid, event, _ = active(); _, result = move_conflict(sid, event); assert result["calendar_revision"] == 1


def test_14_dynamic_conflicts_follow_calendar():
    sid, event, state = active(); assert state["active_request_conflicts"]; move_conflict(sid, event); assert not client.get(f"/api/sessions/{sid}/state").json()["active_request_conflicts"]


def test_15_generated_conflict_ids_are_not_authoritative():
    sid, event, _ = active(); original = set(event["conflicting_event_ids"]); move_conflict(sid, event); assert original and client.get(f"/api/sessions/{sid}/state").json()["accept_available"]


def test_16_infeasible_preview_has_no_profile():
    sid, event, _ = active(); result = client.post(f"/api/sessions/{sid}/previews", json={"event_id": event["scenario_id"], "action": "accept"}).json(); assert not result["feasible"] and "preview_profile" not in result


def test_17_preview_uses_calendar_revision():
    sid, event, _ = active(); move_conflict(sid, event); result = client.post(f"/api/sessions/{sid}/previews", json={"event_id": event["scenario_id"], "action": "accept"}).json(); assert result["feasible"] and result["calendar_revision"] == 1


def test_18_calendar_edit_does_not_update_posterior():
    sid, event, _ = active(); before = sessions.get(sid)["model"].posterior.copy(); move_conflict(sid, event); assert np.array_equal(before, sessions.get(sid)["model"].posterior)


def test_19_repeated_moves_log_once_in_net_adjustment():
    sid, event, _ = active(); conflict, _ = move_conflict(sid, event, 21); day = event["requested_start"][:10]; client.post(f"/api/sessions/{sid}/calendar-actions", json={"action_type": "reschedule_existing", "event_id": conflict["id"], "new_schedule": {"start": f"{day}T22:00:00", "end": f"{day}T23:00:00"}, "source": "calendar_drag"}); decision(sid, event); s = sessions.get(sid); assert len(s["calendar_actions"]) == 2 and len(s["decisions"][-1]["round_calendar_adjustments"]) == 1


def test_20_return_to_original_produces_no_net_adjustment():
    sid, event, _ = active(); s = sessions.get(sid); original = copy.deepcopy(s["calendar"][0]); day = original["start"][:10]; client.post(f"/api/sessions/{sid}/calendar-actions", json={"action_type": "reschedule_existing", "event_id": original["id"], "new_schedule": {"start": f"{day}T21:00:00", "end": f"{day}T22:00:00"}, "source": "calendar_drag"}); client.post(f"/api/sessions/{sid}/calendar-actions", json={"action_type": "reschedule_existing", "event_id": original["id"], "new_schedule": {"start": original["start"], "end": original["end"]}, "source": "calendar_drag"}); decision(sid, event, "decline"); assert not sessions.get(sid)["decisions"][-1]["round_calendar_adjustments"]


def test_21_compound_move_accept_updates_once():
    sid, event, _ = active(); move_conflict(sid, event); version = sessions.get(sid)["version"]; decision(sid, event); assert sessions.get(sid)["version"] == version + 1 and sessions.get(sid)["decisions"][-1]["compound_plan"]["calendar_adjustments"]


def test_22_exact_compound_evidence_is_stored():
    sid, event, _ = active(); conflict, _ = move_conflict(sid, event); decision(sid, event); evidence = sessions.get(sid)["value_evidence"]; assert any(conflict["title"] in item["exact_text"] and event["title"] in item["exact_text"] for item in evidence)


def test_23_export_contains_calendar_audit_fields():
    sid, event, _ = active(); move_conflict(sid, event); decision(sid, event); exported = client.get(f"/api/sessions/{sid}/export").json(); assert all(key in exported for key in ("calendar_actions", "calendar_revision", "round_calendar_before", "round_calendar_adjustments")) and exported["decisions"][-1]["compound_plan"]
