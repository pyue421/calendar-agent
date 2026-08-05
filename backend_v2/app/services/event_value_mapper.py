from __future__ import annotations

import copy

from .value_taxonomy import VALUE_BY_ID

CATEGORY_VALUE_IDS = {
    "wellbeing": "wellbeing",
    "health": "wellbeing",
    "learning": "achievement_growth",
    "work": "achievement_growth",
    "relationships": "relationships_care",
    "social": "relationships_care",
    "focus": "autonomy_privacy",
    "personal": "autonomy_privacy",
    "meeting": "responsibility_fairness",
    "obligation": "responsibility_fairness",
}


def event_value_mapping(event: dict) -> dict:
    value_id = event.get("primary_value_id")
    source = "explicit_template"
    reason = event.get("primary_value_reason") or "This event has an explicit controlled calendar-template mapping."
    if value_id is None:
        value_id = event.get("event_value_id")
        source = "explicit_scenario"
        reason = "This controlled incoming event has an explicit participant-safe scenario mapping."
    if value_id is None:
        value_id = CATEGORY_VALUE_IDS.get(event.get("category"))
        source = "category_mapping"
        reason = f"This event maps deterministically from the controlled category '{event.get('category')}'."
    if value_id not in VALUE_BY_ID:
        return {
            "primary_value_id": None,
            "primary_value_label": None,
            "tone": "neutral",
            "source": "unmapped",
            "reason": "No reliable controlled semantic mapping is available for this event.",
        }
    definition = VALUE_BY_ID[value_id]
    return {
        "primary_value_id": value_id,
        "primary_value_label": definition["label"],
        "tone": definition["tone"],
        "source": source,
        "reason": reason,
    }


def map_calendar_event(event: dict) -> dict:
    mapped = copy.deepcopy(event)
    mapping = event_value_mapping(mapped)
    mapped["value_mapping"] = mapping
    mapped["primary_value_id"] = mapping["primary_value_id"]
    mapped["value_tone"] = mapping["tone"]
    return mapped
