"""Base agent with Anthropic API integration."""

from __future__ import annotations

import json
import logging

import anthropic

import config

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all DISCOVER agents.

    Provides:
      - Anthropic API client initialization
      - call_llm() for free-text responses
      - call_llm_json() for structured JSON responses with fence-stripping
    """

    role: str = "base"
    system_prompt: str = ""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = config.ANTHROPIC_MODEL

    async def call_llm(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Make a call to Claude and return the text response."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or self.system_prompt,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"[{self.role}] LLM call failed: {e}")
            raise

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
