from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol


class CalendarProvider(Protocol):
    def create_calendar(self, session_id: str, week_start: date) -> list[dict]: ...


class DefaultCalendarProvider:
    def __init__(self, path: Path | None = None):
        source = path or Path(__file__).resolve().parents[1] / "data" / "default_calendar.json"
        self.templates = json.loads(source.read_text(encoding="utf-8"))

    def create_calendar(self, session_id: str, week_start: date) -> list[dict]:
        events = []
        for template in self.templates:
            day = week_start + timedelta(days=template["day_index"])
            event = copy.deepcopy(template)
            event["id"] = f"{session_id}_{template['id']}"
            event["start"] = datetime.combine(day, datetime.strptime(template["start_time"], "%H:%M").time()).isoformat()
            event["end"] = datetime.combine(day, datetime.strptime(template["end_time"], "%H:%M").time()).isoformat()
            event["blocks_time"] = template.get("blocks_time", True)
            events.append(event)
        return events


def current_week_start(today: date | None = None) -> date:
    value = today or date.today()
    return value - timedelta(days=value.weekday())


DEFAULT_CALENDAR_PROVIDER = DefaultCalendarProvider()
