from __future__ import annotations

import json
from pathlib import Path

from .bayesian_value_model import VALUE_IDS

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "data" / "calendar_adjustment_features.json").read_text(encoding="utf-8"))


def net_adjustments(before: list[dict], after: list[dict]) -> list[dict]:
    original, final = {e["id"]: e for e in before}, {e["id"]: e for e in after}
    result = []
    for event_id, old in original.items():
        new = final.get(event_id)
        if new is None:
            result.append({"event_id": event_id, "event_title": old["title"], "change_type": "removed",
                           "original_start": old["start"], "original_end": old["end"], "final_start": None, "final_end": None,
                           "protected": old.get("protected", False), "category": old.get("category"), "before": old, "after": None})
        elif old.get("start") != new.get("start") or old.get("end") != new.get("end"):
            result.append({"event_id": event_id, "event_title": new["title"], "change_type": "rescheduled",
                           "original_start": old["start"], "original_end": old["end"], "final_start": new["start"], "final_end": new["end"],
                           "protected": old.get("protected", False), "category": old.get("category"), "before": old, "after": new})
    return result


def adjustment_vector(adjustments: list[dict]) -> list[float]:
    result = [0.0] * len(VALUE_IDS)
    for adjustment in adjustments:
        mapping = CONFIG["category_vectors"].get(adjustment.get("category"), {})
        multiplier = CONFIG[f"{adjustment['change_type']}_multiplier"]
        if adjustment.get("protected"):
            multiplier *= CONFIG["protected_multiplier"]
        for index, value_id in enumerate(VALUE_IDS):
            result[index] += mapping.get(value_id, 0.0) * multiplier
    return result


def compound_features(incoming: dict[str, list[float]], action: str, adjustments: list[dict]) -> dict[str, list[float]]:
    combined = {key: list(value) for key, value in incoming.items()}
    adjustment = adjustment_vector(adjustments)
    combined[action] = [max(-1.0, min(1.0, value + adjustment[index])) for index, value in enumerate(combined[action])]
    return combined
