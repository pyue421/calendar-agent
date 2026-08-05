from __future__ import annotations

import math
from typing import Any

from .value_taxonomy import VALUE_BY_ID, VALUE_IDS

DISPLAY_THRESHOLD = 0.0005


def _profile_by_id(profile: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(profile, list) or len(profile) != len(VALUE_IDS):
        raise ValueError("A profile transition requires exactly five values")
    result = {}
    for item in profile:
        value_id = item.get("id") if isinstance(item, dict) else None
        value = item.get("posterior_mean") if isinstance(item, dict) else None
        if value_id not in VALUE_BY_ID or value_id in result:
            raise ValueError("Profile contains an unknown or duplicate value ID")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ValueError("Profile contains an invalid posterior value")
        result[value_id] = item
    if set(result) != set(VALUE_IDS):
        raise ValueError("Profile is missing a required value ID")
    return result


def compare_profiles(before_profile: list[dict], after_profile: list[dict], *, stage: str, hypothetical: bool,
                     profile_version_before: int, profile_version_after: int | None = None,
                     display_allowed: bool = True, threshold: float = DISPLAY_THRESHOLD, **metadata: Any) -> dict:
    before, after = _profile_by_id(before_profile), _profile_by_id(after_profile)
    changes = []
    for value_id in VALUE_IDS:
        prior = float(before[value_id]["posterior_mean"])
        updated = float(after[value_id]["posterior_mean"])
        delta = updated - prior
        direction = "increase" if delta > threshold else "decrease" if delta < -threshold else "negligible"
        definition = VALUE_BY_ID[value_id]
        changes.append({"value_id": value_id, "display_label": definition["display_label"],
                        "full_label": definition["full_label"], "tone": definition["tone"],
                        "before": prior, "after": updated, "delta": delta,
                        "delta_percentage_points": delta * 100, "absolute_delta": abs(delta),
                        "direction": direction, "changed": direction != "negligible"})
    return {"stage": stage, "hypothetical": hypothetical,
            "profile_version_before": profile_version_before, "profile_version_after": profile_version_after,
            "display_allowed": display_allowed,
            "suppression_reason": None if display_allowed else "profile_not_initialized",
            "changes": changes, **metadata}
