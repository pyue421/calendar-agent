from __future__ import annotations

VALUE_DEFINITIONS = (
    {
        "id": "wellbeing",
        "label": "Wellbeing",
        "tone": "green",
        "description": "Health, rest, boundaries, recovery, and personal sustainability.",
    },
    {
        "id": "achievement_growth",
        "label": "Achievement & Growth",
        "tone": "rose",
        "description": "Progress, mastery, learning, and professional development.",
    },
    {
        "id": "relationships_care",
        "label": "Relationships & Care",
        "tone": "amber",
        "description": "Family, friendship, social support, and community care.",
    },
    {
        "id": "autonomy_privacy",
        "label": "Autonomy & Privacy",
        "tone": "cyan",
        "description": "Control over time, independence, focus, and privacy.",
    },
    {
        "id": "responsibility_fairness",
        "label": "Responsibility & Fairness",
        "tone": "violet",
        "description": "Reliability, cooperation, promises, integrity, and fairness.",
    },
)

VALUE_BY_ID = {definition["id"]: definition for definition in VALUE_DEFINITIONS}
VALUE_IDS = tuple(VALUE_BY_ID)


def value_palette() -> dict[str, dict[str, str]]:
    return {
        value_id: {"label": definition["label"], "tone": definition["tone"]}
        for value_id, definition in VALUE_BY_ID.items()
    }


def exported_taxonomy() -> list[dict]:
    return [dict(definition) for definition in VALUE_DEFINITIONS]
