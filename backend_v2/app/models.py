from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Action = Literal["accept", "decline", "reschedule"]


class Schedule(BaseModel):
    start: str
    end: str


class SessionCreate(BaseModel):
    participant_id: str = ""


class PreviewRequest(BaseModel):
    event_id: str
    action: Action
    candidate_schedule: Schedule | None = None
    display_state: Literal["hover", "focus", "pinned"] = "pinned"

    @model_validator(mode="after")
    def require_candidate(self):
        if self.action == "reschedule" and self.candidate_schedule is None:
            raise ValueError("candidate_schedule is required for reschedule")
        return self


class DecisionRequest(BaseModel):
    event_id: str
    action: Action
    candidate_schedule: Schedule | None = None

    @model_validator(mode="after")
    def require_candidate(self):
        if self.action == "reschedule" and self.candidate_schedule is None:
            raise ValueError("candidate_schedule is required for reschedule")
        return self


class RationaleRequest(BaseModel):
    decision_id: str
    rationale: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class RationaleObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explicit_value_references: list[str] = Field(description="Value IDs explicitly named or directly described by the participant.")
    implicit_value_references: list[str] = Field(description="Value IDs reasonably implied, but not explicitly stated.")
    protected_commitments: list[str] = Field(description="Commitments the participant says the decision protected.")
    compromised_commitments: list[str] = Field(description="Commitments the participant says the decision compromised.")
    constraints: list[str] = Field(description="External constraints or feasibility limits, not inferred values.")
    alternative_explanations: list[str] = Field(description="Plausible non-value explanations or ambiguity that should temper interpretation.")
    directness: Literal["explicit", "implicit", "ambiguous"] = Field(description="How directly the rationale supports the mapped values.")

    @field_validator("explicit_value_references", "implicit_value_references")
    @classmethod
    def validate_value_ids(cls, values: list[str]) -> list[str]:
        allowed = {"wellbeing", "achievement_growth", "relationships_care", "autonomy_privacy", "responsibility_fairness"}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unknown value identifiers: {sorted(unknown)}")
        return list(dict.fromkeys(values))
