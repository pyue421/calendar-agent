from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from pydantic import BaseModel

from ..models import OnboardingEvidenceCandidate, OnboardingReview
from .onboarding_gemini import generate_structured

PROMPT_VERSION = "onboarding_reviewer_v1"
SYSTEM_PROMPT = """Independently evaluate each grounded scheduling-evidence record. Reject unsupported mappings,
identify alternatives, treat one example as limited evidence, do not use posterior weights, and never change the
participant quote. Return structured output only."""


@dataclass(frozen=True)
class ReviewResult:
    reviews: list[OnboardingReview]
    provider: str = "deterministic"
    model: str = "grounding-reviewer-v1"
    raw_output: dict | None = None


class OnboardingEvidenceReviewer(Protocol):
    def review(self, candidates: list[OnboardingEvidenceCandidate], participant_turns: list[dict]) -> ReviewResult: ...


class DeterministicOnboardingEvidenceReviewer:
    def review(self, candidates: list[OnboardingEvidenceCandidate], participant_turns: list[dict]) -> ReviewResult:
        transcript = {turn["message"] for turn in participant_turns}
        reviews = [OnboardingReview(candidate_index=index,
            review_status="accepted" if item.exact_quote in transcript else "rejected",
            review_reason="The quote is present in a participant turn and has a limited keyword-grounded mapping."
                if item.exact_quote in transcript else "The exact quote is not present in the participant transcript.",
            alternative_explanations=item.alternative_explanations) for index, item in enumerate(candidates)]
        return ReviewResult(reviews=reviews, raw_output={"reviews": [item.model_dump() for item in reviews]})


class _ReviewSchema(BaseModel):
    reviews: list[OnboardingReview]


class GeminiOnboardingEvidenceReviewer:
    def __init__(self, config): self.config = config
    def review(self, candidates: list[OnboardingEvidenceCandidate], participant_turns: list[dict]) -> ReviewResult:
        parsed, raw = generate_structured(self.config, SYSTEM_PROMPT,
            f"Participant turns:\n{participant_turns}\nEvidence candidates indexed from zero:\n{[item.model_dump() for item in candidates]}", _ReviewSchema)
        return ReviewResult(parsed.reviews, "gemini", self.config.model, {"raw_json": raw, "reviews": [item.model_dump() for item in parsed.reviews]})
