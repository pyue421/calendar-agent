import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    grid_step: float = float(os.getenv("GRID_STEP", "0.025"))
    prior_family: str = os.getenv("PRIOR_FAMILY", "symmetric_dirichlet")
    prior_alpha: float = float(os.getenv("PRIOR_ALPHA", "1.0"))
    beta: float = float(os.getenv("BETA", "5.0"))
    rationale_reliability: float = float(os.getenv("RATIONALE_RELIABILITY", "0.65"))
    evidence_delta_threshold: float = float(os.getenv("EVIDENCE_DELTA_THRESHOLD", "0.005"))


CONFIG = ModelConfig()


@dataclass(frozen=True)
class LLMConfig:
    parser: str = os.getenv("RATIONALE_PARSER", "gemini")
    api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    timeout_seconds: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
    retry_attempts: int = max(1, int(os.getenv("GEMINI_RETRY_ATTEMPTS", "4")))
    retry_base_seconds: float = max(0.0, float(os.getenv("GEMINI_RETRY_BASE_SECONDS", "1")))
    scenario_generator: str = os.getenv("SCENARIO_GENERATOR", "deterministic")
    onboarding_interviewer: str = os.getenv("ONBOARDING_INTERVIEWER", "deterministic")
    onboarding_extractor: str = os.getenv("ONBOARDING_EXTRACTOR", "deterministic")
    onboarding_reviewer: str = os.getenv("ONBOARDING_REVIEWER", "deterministic")


LLM_CONFIG = LLMConfig()


@dataclass(frozen=True)
class OnboardingConfig:
    enabled: bool = os.getenv("ONBOARDING_ENABLED", "true").lower() in {"1", "true", "yes"}
    evidence_scale: float = float(os.getenv("ONBOARDING_EVIDENCE_SCALE", "0.75"))
    mixture_weight: float = float(os.getenv("ONBOARDING_MIXTURE_WEIGHT", "0.35"))
    score_clip: float = float(os.getenv("ONBOARDING_SCORE_CLIP", "3.0"))
    min_accepted_evidence: int = int(os.getenv("ONBOARDING_MIN_ACCEPTED_EVIDENCE", "2"))
    maximum_turns: int = int(os.getenv("ONBOARDING_MAXIMUM_TURNS", "8"))
    maximum_followups: int = int(os.getenv("ONBOARDING_MAXIMUM_FOLLOWUPS", "2"))

    def __post_init__(self):
        if not 0 <= self.mixture_weight <= 1: raise ValueError("ONBOARDING_MIXTURE_WEIGHT must be between 0 and 1")
        if self.evidence_scale < 0: raise ValueError("ONBOARDING_EVIDENCE_SCALE must be nonnegative")
        if self.score_clip <= 0: raise ValueError("ONBOARDING_SCORE_CLIP must be positive")
        if self.min_accepted_evidence < 0: raise ValueError("ONBOARDING_MIN_ACCEPTED_EVIDENCE must be nonnegative")
        if self.maximum_turns <= 0 or self.maximum_followups <= 0: raise ValueError("Onboarding turn limits must be positive")


ONBOARDING_CONFIG = OnboardingConfig()
