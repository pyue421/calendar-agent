"""Base agent with multi-provider LLM support (Anthropic / Google / Mock)."""

from __future__ import annotations

import json
import logging
import re
import time

import config

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all DISCOVER agents.

    Supports three providers, selected via config.resolve_provider():
      - "anthropic": Claude via the Anthropic API
      - "google":    Gemini via the Google GenAI API (has a free tier)
      - "mock":      Canned responses, no key needed (plumbing tests only)

    Provides:
      - call_llm() for free-text responses
      - call_llm_json() for structured JSON responses with fence-stripping
    """

    role: str = "base"
    system_prompt: str = ""

    def __init__(self):
        self._anthropic_client = None
        self._google_client = None

    # ── Lazy client initialization ───────────────────────────────────

    def _get_anthropic(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(
                api_key=config.ANTHROPIC_API_KEY
            )
        return self._anthropic_client

    def _get_google(self):
        if self._google_client is None:
            from google import genai
            self._google_client = genai.Client(api_key=config.GOOGLE_API_KEY)
        return self._google_client

    # ── Public API ───────────────────────────────────────────────────

    async def call_llm(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Make an LLM call and return the text response."""
        provider = config.resolve_provider()

        if provider == "mock":
            from mock_llm import mock_response
            logger.info(f"[{self.role}] MOCK MODE — returning canned response")
            return mock_response(
                self.role, expect_json=False,
                round_num=self._extract_round_num(messages),
            )

        if provider == "google":
            return self._call_google(messages, system, max_tokens, temperature)

        return self._call_anthropic(messages, system, max_tokens, temperature)

    async def call_llm_json(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.5,
    ) -> dict:
        """Call LLM and parse the result as JSON.

        Handles markdown fences and partial JSON extraction.
        """
        provider = config.resolve_provider()
        if provider == "mock":
            from mock_llm import mock_response
            logger.info(f"[{self.role}] MOCK MODE — returning canned JSON")
            return json.loads(mock_response(
                self.role, expect_json=True,
                round_num=self._extract_round_num(messages),
            ))

        raw = await self.call_llm(messages, system, max_tokens, temperature)
        text = raw.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON object from surrounding text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise ValueError(
                f"[{self.role}] Could not parse JSON from response: {text[:200]}"
            )

    # ── Provider implementations ─────────────────────────────────────

    def _call_anthropic(
        self,
        messages: list[dict],
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        try:
            client = self._get_anthropic()
            response = client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or self.system_prompt,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"[{self.role}] Anthropic call failed: {e}")
            raise

    def _call_google(
        self,
        messages: list[dict],
        system: str | None,
        max_tokens: int,
        temperature: float,
        max_retries: int = 3,
    ) -> str:
        """Call Gemini via the Google GenAI SDK.

        Converts Anthropic-style messages to Gemini format and retries
        on rate limits (free tier is ~10-15 requests/minute).
        """
        from google.genai import types

        client = self._get_google()

        # Convert Anthropic-style messages to Gemini contents
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])],
                )
            )

        gen_config = types.GenerateContentConfig(
            system_instruction=system or self.system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        last_error = None
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=config.GOOGLE_MODEL,
                    contents=contents,
                    config=gen_config,
                )
                if response.text is None:
                    raise ValueError("Empty response from Gemini")
                return response.text
            except Exception as e:
                last_error = e
                error_str = str(e)
                # Retry on rate limits (429) with backoff — free tier is limited
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait = 15 * (attempt + 1)
                    logger.warning(
                        f"[{self.role}] Gemini rate limit hit, "
                        f"waiting {wait}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait)
                    continue
                logger.error(f"[{self.role}] Google call failed: {e}")
                raise

        logger.error(f"[{self.role}] Google call failed after {max_retries} retries")
        raise last_error

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_round_num(messages: list[dict]) -> int:
        """Best-effort extraction of the round number from prompt text."""
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                m = re.search(r"[Rr]ound\s+(\d+)", content)
                if m:
                    return int(m.group(1))
        return 1