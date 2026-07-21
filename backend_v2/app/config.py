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
    model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    timeout_seconds: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
    scenario_generator: str = os.getenv("SCENARIO_GENERATOR", "deterministic")


LLM_CONFIG = LLMConfig()
