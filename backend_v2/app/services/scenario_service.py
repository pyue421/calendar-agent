from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from google import genai
from google.genai import types

from ..config import LLM_CONFIG, LLMConfig
from ..llm.rationale_parser import gemini_compatible_schema


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class GeneratedScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    module_id: str
    scenario_family: str
    requester: str
    title: str
    description: str
    requested_start: str
    requested_end: str
    conflicting_event_ids: list[str]
    feasible_actions: list[str]


class SurfaceDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requester: str
    title: str
    request_text: str


class ScenarioBank:
    def __init__(self, path: Path = DATA_DIR / "scenario_bank.json"):
        self.scenarios = json.loads(path.read_text(encoding="utf-8"))
        if len(self.scenarios) != 15 or len({s["scenario_id"] for s in self.scenarios}) != 15:
            raise ValueError("Scenario bank must contain exactly 15 unique scenarios")
        self.by_id = {s["scenario_id"]: s for s in self.scenarios}

    def get(self, scenario_id: str) -> dict:
        return self.by_id[scenario_id]


class ScenarioGenerator:
    """Generates surface details only; experimental structure is always copied from the bank."""

    def __init__(self, config: LLMConfig = LLM_CONFIG):
        self.config = config

    def _surface(self, specification: dict, current_round: int, participant_context: dict | None) -> SurfaceDetails:
        fallback = SurfaceDetails(requester=specification["requester"], title=specification["title"], request_text=specification["request_text"])
        if self.config.scenario_generator == "deterministic" or not self.config.api_key:
            return fallback
        if self.config.scenario_generator != "gemini":
            raise ValueError("SCENARIO_GENERATOR must be 'gemini' or 'deterministic'")
        prompt = (
            "Personalize only the surface wording of this controlled calendar request. Do not mention values, "
            "experimental conditions, or hidden trade-offs. Keep the request realistic and concise.\n"
            f"Round: {current_round}\nInstructions: {specification['generator_instructions']}\n"
            f"Safe participant context: {participant_context or {}}"
        )
        try:
            client = genai.Client(api_key=self.config.api_key, http_options=types.HttpOptions(timeout=int(self.config.timeout_seconds * 1000)))
            response = client.models.generate_content(model=self.config.model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json",
                    response_schema=gemini_compatible_schema(SurfaceDetails.model_json_schema()), temperature=0.4))
            return SurfaceDetails.model_validate_json(response.text)
        except Exception:
            return fallback

    def generate(self, specification: dict, calendar: list[dict], current_round: int, participant_context: dict | None = None) -> GeneratedScenario:
        surface = self._surface(specification, current_round, participant_context)
        base = datetime(2026, 7, 21, specification["hour"])
        start = base + timedelta(days=specification["day_offset"] - 1)
        end = start + timedelta(minutes=specification["duration_minutes"])
        conflicts = [e["id"] for e in calendar if datetime.fromisoformat(e["start"]) < end and datetime.fromisoformat(e["end"]) > start]
        if not conflicts:
            conflict = {
                "id": f"conflict_{specification['scenario_id']}",
                "title": specification["required_calendar_conflict"].replace("_", " ").title(),
                "start": start.isoformat(), "end": end.isoformat(), "category": "protected", "protected": True,
            }
            calendar.append(conflict)
            conflicts = [conflict["id"]]
        return GeneratedScenario(
            scenario_id=specification["scenario_id"], module_id=specification["module_id"],
            scenario_family=specification["scenario_family"], requester=surface.requester,
            title=surface.title, description=surface.request_text,
            requested_start=start.isoformat(), requested_end=end.isoformat(),
            conflicting_event_ids=conflicts, feasible_actions=specification["feasible_actions"],
        )


BANK = ScenarioBank()
GENERATOR = ScenarioGenerator()
