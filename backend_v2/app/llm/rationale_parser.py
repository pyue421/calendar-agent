from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import types

from ..config import LLMConfig
from ..models import RationaleObservation
from ..services.bayesian_value_model import VALUE_IDS


SYSTEM_PROMPT = """You convert a participant's explanation of one calendar decision into structured evidence.
This is a reflection intervention, not an assessment of objectively true values.

Use only the participant rationale and the supplied factual decision context. Never infer evidence from an
assistant message. Do not assign weights, scores, confidence numbers, or psychological traits. Separate external
constraints from values. Preserve ambiguity and include plausible non-value explanations when warranted.

Allowed value identifiers and participant-facing meanings:
- wellbeing: health, rest, energy, sustainable pace
- achievement: completing goals, productivity, accomplishment
- reliability: keeping promises, punctuality, dependability
- relationships: caring for and maintaining personal relationships
- autonomy: choice, control, self-direction
- collaboration: coordinating and working with others
- fairness: equitable distribution of burden or opportunity
- growth: learning, practice, development
- privacy: control over personal information or solitude
- community_contribution: helping a wider group or community
- boundaries: protecting personal time or role limits
- security: safety, stability, risk reduction

Only return value identifiers from this vocabulary. Quote or closely paraphrase commitments and constraints from
the participant; do not invent them. Explicit references are directly stated. Implicit references require a clear
but unstated connection. When evidence is weak, use directness='ambiguous' and alternative_explanations.
"""


class RationaleParserError(RuntimeError):
    pass


class RationaleParserConfigurationError(RationaleParserError):
    pass


@dataclass(frozen=True)
class ParseResult:
    observation: RationaleObservation
    provider: str
    model: str


class RationaleParser(Protocol):
    def parse(self, text: str, decision_context: dict) -> ParseResult: ...


class GeminiRationaleParser:
    def __init__(self, config: LLMConfig):
        self.config = config

    def parse(self, text: str, decision_context: dict) -> ParseResult:
        if not self.config.api_key:
            raise RationaleParserConfigurationError(
                "GEMINI_API_KEY is not configured. Add it to backend_v2/.env and restart the backend."
            )
        client = genai.Client(api_key=self.config.api_key, http_options=types.HttpOptions(timeout=int(self.config.timeout_seconds * 1000)))
        prompt = (
            f"Committed calendar action: {decision_context['action']}\n"
            f"Candidate schedule: {decision_context.get('candidate_schedule') or 'not applicable'}\n"
            f"Participant rationale (the only conversational evidence):\n{text}"
        )
        try:
            response = client.models.generate_content(
                model=self.config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    # Pydantic's extra="forbid" emits `additionalProperties: false`.
                    # Some Gemini generateContent schema versions reject that keyword,
                    # so send a compatible schema and retain strict validation below.
                    response_schema=gemini_compatible_schema(RationaleObservation.model_json_schema()),
                    temperature=0,
                ),
            )
            if not response.text:
                raise RationaleParserError("Gemini returned an empty rationale observation.")
            observation = RationaleObservation.model_validate_json(response.text)
            return ParseResult(observation=observation, provider="gemini", model=self.config.model)
        except RationaleParserError:
            raise
        except Exception as exc:
            raise RationaleParserError(f"Gemini rationale parsing failed: {exc}") from exc


KEYWORDS = {
    "wellbeing": ("rest", "health", "wellbeing", "energy"), "achievement": ("deadline", "work", "finish", "productive"),
    "reliability": ("promise", "committed", "reliable", "on time"), "relationships": ("family", "friend", "relationship"),
    "autonomy": ("choice", "control", "prefer"), "collaboration": ("team", "together", "collaborate"),
    "fairness": ("fair", "equal"), "growth": ("learn", "growth", "practice"), "privacy": ("private", "privacy"),
    "community_contribution": ("community", "volunteer"), "boundaries": ("boundary", "personal time", "outside work"),
    "security": ("safe", "security", "risk"),
}


class DeterministicRationaleParser:
    """Explicit offline/test fallback. Production defaults to Gemini."""

    def parse(self, text: str, decision_context: dict) -> ParseResult:
        del decision_context
        lower = text.lower()
        explicit = [v for v in VALUE_IDS if v.replace("_", " ") in lower]
        implicit = [v for v, words in KEYWORDS.items() if v not in explicit and any(word in lower for word in words)]
        constraints = [s.strip() for s in re.split(r"[.;]", text) if any(k in s.lower() for k in ("can't", "cannot", "must", "because", "conflict"))]
        directness = "explicit" if explicit else "implicit" if implicit else "ambiguous"
        observation = RationaleObservation(
            explicit_value_references=explicit, implicit_value_references=implicit,
            protected_commitments=constraints, compromised_commitments=[], constraints=constraints,
            alternative_explanations=[] if implicit or explicit else ["The rationale did not map confidently to the fixed vocabulary."],
            directness=directness,
        )
        return ParseResult(observation=observation, provider="deterministic", model="keyword-fallback-v1")


def build_rationale_parser(config: LLMConfig) -> RationaleParser:
    if config.parser == "gemini":
        return GeminiRationaleParser(config)
    if config.parser == "deterministic":
        return DeterministicRationaleParser()
    raise RationaleParserConfigurationError("RATIONALE_PARSER must be 'gemini' or 'deterministic'.")


def gemini_compatible_schema(schema: dict) -> dict:
    """Remove JSON Schema keywords rejected by Gemini's generateContent schema API."""
    if isinstance(schema, dict):
        return {
            key: gemini_compatible_schema(value)
            for key, value in schema.items()
            if key != "additionalProperties"
        }
    if isinstance(schema, list):
        return [gemini_compatible_schema(value) for value in schema]
    return schema
