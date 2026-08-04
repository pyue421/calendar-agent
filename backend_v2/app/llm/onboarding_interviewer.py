from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from pydantic import BaseModel
from .onboarding_gemini import generate_structured

PROMPT_VERSION = "onboarding_interviewer_v1"
SYSTEM_PROMPT = """You support a standardized scheduling-priority conversation, not a psychological diagnosis.
Use only approved protocol follow-ups. Do not infer, score, output, or mention values or hidden categories. Do not
pressure skipped questions. Keep acknowledgements short and neutral. Return structured output only."""


@dataclass(frozen=True)
class InterviewResult:
    acknowledgement: str
    selected_followup_id: str | None
    should_ask_followup: bool
    provider: str = "deterministic"
    model: str = "protocol-controller-v1"


class OnboardingInterviewer(Protocol):
    def respond(self, answer: str, question_id: str, remaining_followups: int) -> InterviewResult: ...


class DeterministicOnboardingInterviewer:
    def respond(self, answer: str, question_id: str, remaining_followups: int) -> InterviewResult:
        del question_id
        ask = remaining_followups > 0 and len(answer.split()) < 6
        return InterviewResult("Thank you for sharing that.", "ask_for_reason" if ask else None, ask)


class _InterviewSchema(BaseModel):
    acknowledgement: str
    selected_followup_id: str | None
    should_ask_followup: bool


class GeminiOnboardingInterviewer:
    def __init__(self, config): self.config = config
    def respond(self, answer: str, question_id: str, remaining_followups: int) -> InterviewResult:
        parsed, _ = generate_structured(self.config, SYSTEM_PROMPT,
            f"Question ID: {question_id}\nParticipant answer: {answer}\nRemaining follow-ups: {remaining_followups}\nApproved follow-up IDs: ask_for_reason, ask_about_tradeoff, ask_about_stability, ask_about_consequence",
            _InterviewSchema)
        allowed = {"ask_for_reason", "ask_about_tradeoff", "ask_about_stability", "ask_about_consequence"}
        ask = parsed.should_ask_followup and remaining_followups > 0 and parsed.selected_followup_id in allowed
        return InterviewResult(parsed.acknowledgement, parsed.selected_followup_id if ask else None, ask, "gemini", self.config.model)
