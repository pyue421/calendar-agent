from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from pydantic import BaseModel

from ..models import OnboardingEvidenceCandidate
from .rationale_parser import KEYWORDS
from .onboarding_gemini import generate_structured
from ..services.value_taxonomy import exported_taxonomy

PROMPT_VERSION = "onboarding_extractor_v1"
SYSTEM_PROMPT = """Use participant messages only and require exact grounded quotes. Map only to the fixed five
scheduling-priority IDs. Separate values from constraints, preserve ambiguity, and never output probabilities,
numeric confidence, diagnoses, or traits outside scheduling contexts. Return structured output only."""


@dataclass(frozen=True)
class ExtractionResult:
    evidence: list[OnboardingEvidenceCandidate]
    provider: str = "deterministic"
    model: str = "keyword-extractor-v1"
    raw_output: dict | None = None


class OnboardingEvidenceExtractor(Protocol):
    def extract(self, participant_turns: list[dict]) -> ExtractionResult: ...


class DeterministicOnboardingEvidenceExtractor:
    def extract(self, participant_turns: list[dict]) -> ExtractionResult:
        evidence = []
        for turn in participant_turns:
            quote = turn["message"]
            lower = quote.lower()
            for value_id, keywords in KEYWORDS.items():
                if any(keyword in lower for keyword in keywords):
                    evidence.append(OnboardingEvidenceCandidate(turn_id=turn["turn_id"], question_id=turn["question_id"],
                        exact_quote=quote, value_id=value_id, relation="supports", directness="implicit",
                        strength="moderate", alternative_explanations=["One scheduling example may not represent a stable general priority."]))
        return ExtractionResult(evidence=evidence, raw_output={"evidence": [item.model_dump() for item in evidence]})


class _ExtractionSchema(BaseModel):
    evidence: list[OnboardingEvidenceCandidate]


class GeminiOnboardingEvidenceExtractor:
    def __init__(self, config): self.config = config
    def extract(self, participant_turns: list[dict]) -> ExtractionResult:
        parsed, raw = generate_structured(self.config, SYSTEM_PROMPT,
            f"Fixed versioned taxonomy:\n{exported_taxonomy()}\nParticipant turns with question and turn IDs:\n{participant_turns}", _ExtractionSchema)
        return ExtractionResult(parsed.evidence, "gemini", self.config.model, {"raw_json": raw, "evidence": [item.model_dump() for item in parsed.evidence]})
