from __future__ import annotations

import time

from google import genai
from google.genai import types

from .rationale_parser import (RationaleParserConfigurationError, RationaleParserError,
                               RationaleParserUnavailableError, _is_transient_gemini_error,
                               gemini_compatible_schema)


def generate_structured(config, system_prompt: str, prompt: str, response_model):
    if not config.api_key: raise RationaleParserConfigurationError("GEMINI_API_KEY is required for Gemini onboarding roles.")
    client = genai.Client(api_key=config.api_key, http_options=types.HttpOptions(timeout=int(config.timeout_seconds * 1000)))
    for attempt in range(config.retry_attempts):
        try:
            response = client.models.generate_content(model=config.model, contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json",
                    response_schema=gemini_compatible_schema(response_model.model_json_schema()), temperature=0))
            if not response.text: raise RationaleParserError("Gemini returned an empty onboarding response.")
            return response_model.model_validate_json(response.text), response.text
        except RationaleParserError: raise
        except Exception as exc:
            if not _is_transient_gemini_error(exc): raise RationaleParserError(f"Gemini onboarding call failed: {exc}") from exc
            if attempt + 1 == config.retry_attempts: raise RationaleParserUnavailableError("Gemini onboarding is temporarily unavailable; retry or choose the neutral prior.") from exc
            time.sleep(config.retry_base_seconds * (2 ** attempt))
