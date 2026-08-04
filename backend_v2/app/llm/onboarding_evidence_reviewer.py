from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from pydantic import BaseModel

from ..models import OnboardingEvidenceCandidate, OnboardingReview
from .onboarding_gemini import generate_structured
from ..services.value_taxonomy import TAXONOMY_VERSION, exported_taxonomy
from ..services.onboarding_evidence_service import validate_grounded_evidence_candidate

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
    taxonomy_version: str = TAXONOMY_VERSION


class OnboardingEvidenceReviewer(Protocol):
    def review(self, candidates: list[OnboardingEvidenceCandidate], participant_turns: list[dict]) -> ReviewResult: ...


class DeterministicOnboardingEvidenceReviewer:
    def review(self, candidates: list[OnboardingEvidenceCandidate], participant_turns: list[dict]) -> ReviewResult:
        reviews = []
        for index, item in enumerate(candidates):
            try:
                validate_grounded_evidence_candidate(item, participant_turns); grounded = True
            except ValueError:
                grounded = False
            reviews.append(OnboardingReview(candidate_index=index, review_status="accepted" if grounded else "rejected",
                review_reason="The quote is grounded in its identified participant turn and has a limited keyword mapping."
                    if grounded else "The quote is not grounded in its identified participant turn.",
                alternative_explanations=item.alternative_explanations))
        return ReviewResult(reviews=reviews, raw_output={"reviews": [item.model_dump() for item in reviews]})


class _ReviewSchema(BaseModel):
    reviews: list[OnboardingReview]


class GeminiOnboardingEvidenceReviewer:
    def __init__(self, config): self.config = config
    def review(self, candidates: list[OnboardingEvidenceCandidate], participant_turns: list[dict]) -> ReviewResult:
        taxonomy = exported_taxonomy()
        parsed, raw = generate_structured(self.config, SYSTEM_PROMPT,
            f"Versioned scheduling-priority taxonomy ({TAXONOMY_VERSION}):\n{taxonomy}\n"
            f"Participant turns:\n{participant_turns}\nEvidence candidates indexed from zero:\n{[item.model_dump() for item in candidates]}", _ReviewSchema)
        return ReviewResult(parsed.reviews, "gemini", self.config.model,
            {"raw_json": raw, "reviews": [item.model_dump() for item in parsed.reviews],
             "taxonomy_version": TAXONOMY_VERSION}, TAXONOMY_VERSION)
