"""DISCOVER framework configuration."""

import os
from pathlib import Path

# ── API ──────────────────────────────────────────────────────────────
# Provider: "anthropic" | "google" | auto-detected from available keys
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")

# Mock mode: run the full pipeline with canned responses (no API key needed).
# Tests plumbing only — NOT inference quality.
USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "").lower() in ("true", "1", "yes")


def resolve_provider() -> str:
    """Determine which LLM provider to use based on config and available keys."""
    if USE_MOCK_LLM:
        return "mock"
    if LLM_PROVIDER in ("anthropic", "google"):
        return LLM_PROVIDER
    # Auto-detect from available keys
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if GOOGLE_API_KEY:
        return "google"
    return "mock"

# ── Server ───────────────────────────────────────────────────────────
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:5176", "http://127.0.0.1:5173"]

# ── Session ──────────────────────────────────────────────────────────
TOTAL_ROUNDS = 15
EXPLORATION_ROUNDS = range(1, 6)      # Rounds 1-5
PROBING_ROUNDS = range(6, 11)         # Rounds 6-10
STRESS_TEST_ROUNDS = range(11, 16)    # Rounds 11-15
REFLECTION_ROUNDS = {5, 10, 15}       # Touchpoints

# ── Ladder of Abstraction levels ─────────────────────────────────────
ABSTRACTION_LEVELS = [
    "raw_action",            # e.g., "declined meeting at 7pm"
    "behavioral_pattern",    # e.g., "consistently protects evenings"
    "scheduling_priority",   # e.g., "personal time over work extension"
    "abstract_value",        # e.g., "work-life boundaries"
]

# ── Persistence ──────────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DISCOVER_DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── .env loading ─────────────────────────────────────────────────────
def load_env():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value
    # Re-read after loading
    global ANTHROPIC_API_KEY, GOOGLE_API_KEY, LLM_PROVIDER, USE_MOCK_LLM
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()
    USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "").lower() in ("true", "1", "yes")
    # Auto-enable mock mode if no key from any provider is present
    if not ANTHROPIC_API_KEY and not GOOGLE_API_KEY:
        USE_MOCK_LLM = True