from __future__ import annotations

from datetime import datetime

from .bayesian_value_model import VALUE_IDS


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
            autonomy=0.45, collaboration=max(0.05, 0.55 - delay_days * 0.08),
            reliability=max(0.05, 0.5 - delay_days * 0.1), wellbeing=0.35 if not outside_hours else -0.35,
            boundaries=-0.55 if outside_hours or protected else 0.25, relationships=-0.25 * conflicts,
            fairness=-0.2 * conflicts, achievement=0.25 if conflicts == 0 else -0.2,
        )
    return features
