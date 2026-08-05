from __future__ import annotations

from datetime import datetime, timezone


class InvalidScheduleError(ValueError):
    pass


class CalendarConflictError(ValueError):
    def __init__(self, conflicts: list[dict]):
        super().__init__("The selected time overlaps existing events.")
        self.conflicts = conflicts

    def detail(self) -> dict:
        return {"code": "calendar_conflict", "message": str(self), "conflicts": self.conflicts}


def parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise InvalidScheduleError("Schedule values must be complete ISO datetimes") from exc
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def validate_interval(start: str, end: str) -> tuple[datetime, datetime]:
    first, last = parse_datetime(start), parse_datetime(end)
    if last <= first:
        raise InvalidScheduleError("Schedule end must be later than start")
    return first, last


def conflict_summary(event: dict) -> dict:
    return {key: event.get(key) for key in (
        "id", "title", "start", "end", "category", "protected", "primary_value_id", "value_tone", "value_mapping"
    )}


def find_conflicts(calendar: list[dict], start: str, end: str, exclude_event_id: str | None = None) -> list[dict]:
    candidate_start, candidate_end = validate_interval(start, end)
    conflicts = []
    for event in calendar:
        if event.get("id") == exclude_event_id or event.get("temporary") or not event.get("blocks_time", True):
            continue
        existing_start, existing_end = validate_interval(event["start"], event["end"])
        if candidate_start < existing_end and candidate_end > existing_start:
            conflicts.append(conflict_summary(event))
    return conflicts


def is_schedule_available(calendar: list[dict], start: str, end: str, exclude_event_id: str | None = None) -> bool:
    return not find_conflicts(calendar, start, end, exclude_event_id)
