from __future__ import annotations

from datetime import datetime

from .value_taxonomy import VALUE_IDS


def _vector(**values: float) -> list[float]:
    return [values.get(key, 0.0) for key in VALUE_IDS]


def action_features(scenario: dict, candidate_schedule: dict | None = None) -> dict[str, list[float]]:
    predefined = scenario["action_features"]
    features = {name: _vector(**mapping) for name, mapping in predefined.items()}
    if candidate_schedule:
        requested = datetime.fromisoformat(scenario["requested_start"])
        start = datetime.fromisoformat(candidate_schedule["start"])
        delay_days = max(0.0, (start - requested).total_seconds() / 86400)
        conflicts = sum(
            datetime.fromisoformat(e["start"]) < datetime.fromisoformat(candidate_schedule["end"])
            and datetime.fromisoformat(e["end"]) > start for e in scenario.get("calendar", [])
        )
        outside_hours = start.hour < 8 or start.hour >= 18
        protected = any(e.get("protected") and datetime.fromisoformat(e["start"]) < datetime.fromisoformat(candidate_schedule["end"])
                        and datetime.fromisoformat(e["end"]) > start for e in scenario.get("calendar", []))
        features["reschedule"] = _vector(
            wellbeing=0.4 if not outside_hours else -0.6,
            achievement_growth=max(-0.5, 0.35 - delay_days * 0.08 - conflicts * 0.15),
            relationships_care=max(-0.5, 0.25 - conflicts * 0.2),
            autonomy_privacy=-0.6 if protected else (0.45 if not outside_hours else -0.25),
            responsibility_fairness=max(-0.5, 0.55 - delay_days * 0.1 - conflicts * 0.2),
        )
    return features
