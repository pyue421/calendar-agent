SCENARIO = {
    "id": "event_123",
    "title": "Project review request",
    "requester": "Maya Chen",
    "requested_start": "2026-07-22T15:30:00",
    "requested_end": "2026-07-22T16:30:00",
    "description": "Maya asks for a project review during a protected focus block.",
    "calendar": [
        {"id": "cal_1", "title": "Deep work", "start": "2026-07-22T15:00:00", "end": "2026-07-22T17:00:00", "category": "work", "protected": True},
        {"id": "cal_2", "title": "Dinner", "start": "2026-07-22T18:30:00", "end": "2026-07-22T19:30:00", "category": "personal", "protected": True},
        {"id": "cal_3", "title": "Team planning", "start": "2026-07-23T10:00:00", "end": "2026-07-23T11:00:00", "category": "work", "protected": False},
    ],
    "action_features": {
        "accept": {"collaboration": 0.7, "reliability": 0.45, "achievement": 0.3, "boundaries": -0.55, "autonomy": -0.2},
        "decline": {"boundaries": 0.75, "autonomy": 0.55, "wellbeing": 0.35, "collaboration": -0.45, "relationships": -0.2},
        "reschedule": {"collaboration": 0.5, "boundaries": 0.4, "autonomy": 0.4, "reliability": 0.25},
    },
    "experimental_metadata": {"condition": "counterfactual-preview", "feature_balance_key": "c2"},
}


def participant_scenario() -> dict:
    return {key: value for key, value in SCENARIO.items() if key not in {"action_features", "experimental_metadata"}}

