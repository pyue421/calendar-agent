import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    particle_count: int = 800
    beta: float = 5.0
    rationale_reliability: float = 0.65
    resample_ess_ratio: float = 0.45
    seed: int = 421


CONFIG = ModelConfig()


@dataclass(frozen=True)
class LLMConfig:
    parser: str = os.getenv("RATIONALE_PARSER", "gemini")
    api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    timeout_seconds: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))


LLM_CONFIG = LLMConfig()
