import json
from types import SimpleNamespace

import pytest

from app.config import LLMConfig
from app.llm import rationale_parser
from app.llm.rationale_parser import GeminiRationaleParser, RationaleParserUnavailableError


OBSERVATION = {
    "explicit_value_references": ["wellbeing"],
    "implicit_value_references": [],
    "protected_commitments": ["rest"],
    "compromised_commitments": [],
    "constraints": [],
    "alternative_explanations": [],
    "directness": "explicit",
}


class TransientError(Exception):
    code = 503


def parser(attempts=3):
    return GeminiRationaleParser(LLMConfig(
        parser="gemini", api_key="test-key", model="test-model", timeout_seconds=1,
        retry_attempts=attempts, retry_base_seconds=0, scenario_generator="deterministic",
    ))


def test_transient_503_is_retried(monkeypatch):
    calls = iter([TransientError("UNAVAILABLE"), SimpleNamespace(text=json.dumps(OBSERVATION))])

    class Models:
        def generate_content(self, **_kwargs):
            result = next(calls)
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(rationale_parser.genai, "Client", lambda **_kwargs: SimpleNamespace(models=Models()))
    result = parser().parse("I needed rest.", {"action": "decline"})
    assert result.observation.explicit_value_references == ["wellbeing"]


def test_exhausted_transient_retries_raise_retryable_error(monkeypatch):
    class Models:
        def generate_content(self, **_kwargs):
            raise TransientError("503 UNAVAILABLE")

    monkeypatch.setattr(rationale_parser.genai, "Client", lambda **_kwargs: SimpleNamespace(models=Models()))
    with pytest.raises(RationaleParserUnavailableError, match="temporarily unavailable"):
        parser(attempts=2).parse("I needed rest.", {"action": "decline"})
