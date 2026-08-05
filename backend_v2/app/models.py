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


class OnboardingMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class OnboardingSkipRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=100)


class InitialProfileViewedRequest(BaseModel):
    profile_version: int = Field(ge=0)
    displayed_at: str
    source: Literal["values_panel"]


class ProfileInteractionRequest(BaseModel):
    event_type: Literal["value_bubble_opened", "value_evidence_opened", "value_modal_closed"]
    value_id: str
    profile_version: int = Field(ge=0)
    profile_stage: str
    round: int = Field(ge=0)
    timestamp: str
    source_phase: str

    @field_validator("value_id")
    @classmethod
    def interaction_value_id(cls, value: str) -> str:
        allowed = {"wellbeing", "achievement_growth", "relationships_care", "autonomy_privacy", "responsibility_fairness"}
        if value not in allowed: raise ValueError("Unknown value identifier")
        return value


class OnboardingEvidenceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_id: str
    question_id: str
    exact_quote: str = Field(min_length=1)
    value_id: str
    relation: Literal["supports", "challenges"]
    directness: Literal["explicit", "implicit", "ambiguous"]
    strength: Literal["weak", "moderate", "strong"]
    alternative_explanations: list[str] = Field(default_factory=list)

    @field_validator("value_id")
    @classmethod
    def onboarding_value_id(cls, value: str) -> str:
        allowed = {"wellbeing", "achievement_growth", "relationships_care", "autonomy_privacy", "responsibility_fairness"}
        if value not in allowed: raise ValueError("Unknown onboarding value identifier")
        return value


class OnboardingReview(BaseModel):
    candidate_index: int = Field(ge=0)
    review_status: Literal["accepted", "ambiguous", "rejected"]
    review_reason: str
    alternative_explanations: list[str] = Field(default_factory=list)


class CalendarActionRequest(BaseModel):
    action_type: Literal["reschedule_existing", "remove_existing", "modify_existing"]
    event_id: str
    new_schedule: Schedule | None = None
    changes: dict | None = None
    source: Literal["calendar_drag", "calendar_event_modal"]

    @model_validator(mode="after")
    def validate_payload(self):
        if self.action_type == "reschedule_existing" and self.new_schedule is None:
            raise ValueError("new_schedule is required for reschedule_existing")
        if self.action_type == "modify_existing" and not self.changes:
            raise ValueError("changes are required for modify_existing")
        return self


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
