from __future__ import annotations

TAXONOMY_VERSION = "scheduling-priorities-v1.1"

# The participant-facing labels are concise interface aliases for
# domain-specific scheduling-priority constructs. They should not be interpreted
# as independently validated psychological scales.
VALUE_DEFINITIONS = (
    {"id": "wellbeing", "display_label": "Wellbeing", "full_label": "Wellbeing",
     "definition": "Health, rest, boundaries, recovery, and personal sustainability.",
     "theoretical_notes": "A domain-specific scheduling-priority construct concerning sustainable personal functioning.", "tone": "green"},
    {"id": "achievement_growth", "display_label": "Achievement", "full_label": "Achievement and Development",
     "definition": "Progress, learning, skill development, and professional development.",
     "theoretical_notes": "A composite scheduling-priority construct; the interface alias is not a claim of equivalence to competence or mastery scales.", "tone": "rose"},
    {"id": "relationships_care", "display_label": "Relationships", "full_label": "Relationships and Care",
     "definition": "Family, friendship, social support, and community care.",
     "theoretical_notes": "A composite scheduling-priority construct spanning interpersonal connection and care commitments.", "tone": "amber"},
    {"id": "autonomy_privacy", "display_label": "Autonomy", "full_label": "Autonomy and Privacy",
     "definition": "Control over time, independence, focus, and privacy.",
     "theoretical_notes": "A composite scheduling-priority construct spanning time control, independence, focus, and privacy.", "tone": "cyan"},
    {"id": "responsibility_fairness", "display_label": "Responsibility", "full_label": "Responsibility and Fairness",
     "definition": "Reliability, cooperation, promises, integrity, and fairness.",
     "theoretical_notes": "A composite scheduling-priority construct spanning obligations, cooperation, integrity, and fairness.", "tone": "violet"},
)

# Compatibility aliases keep existing API clients working while all terminology
# remains authored in this single versioned taxonomy.
for definition in VALUE_DEFINITIONS:
    definition["label"] = definition["display_label"]
    definition["description"] = definition["definition"]
    definition["taxonomy_version"] = TAXONOMY_VERSION

VALUE_BY_ID = {definition["id"]: definition for definition in VALUE_DEFINITIONS}
VALUE_IDS = tuple(VALUE_BY_ID)


def value_palette() -> dict[str, dict[str, str]]:
    return {value_id: {"label": definition["display_label"], "display_label": definition["display_label"],
                       "full_label": definition["full_label"], "tone": definition["tone"]}
            for value_id, definition in VALUE_BY_ID.items()}


def exported_taxonomy() -> list[dict]:
    return [dict(definition) for definition in VALUE_DEFINITIONS]
