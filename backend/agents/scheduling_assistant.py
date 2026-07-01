"""Scheduling Assistant — the participant-facing conversational agent.

Manages the calendar interaction, presents scheduling scenarios,
and serves as the primary interface. Collects both behavioral signals
(what the user does) and conversational signals (what they say about why).

Key design choices:
- Asks clarifying questions that surface rationale without leading
- Mirrors back observations neutrally to encourage elaboration
- Never directly asks "what are your values?" — the whole point is
  that values leak through task behavior
- Logs all exchanges for post-hoc signal decomposition
"""

from __future__ import annotations

import json

from agents import BaseAgent
from models import (
    CalendarEvent,
    ConversationalSignal,
    EmailMessage,
    Session,
)


class SchedulingAssistant(BaseAgent):
    role = "scheduling_assistant"

    system_prompt = """\
You are a helpful calendar scheduling assistant for a working professional.
You help them manage their weekly schedule, respond to incoming meeting
requests, and resolve scheduling conflicts.

BEHAVIORAL GUIDELINES:
1. Be warm, professional, and concise. No more than 2-3 short paragraphs.
2. When presenting a scheduling conflict, lay out the trade-offs neutrally.
   Never make the decision for the user — present options and ask what they
   would prefer.
3. When the user makes a scheduling decision, gently ask a brief follow-up
   about their reasoning. Use natural language like:
   - "Got it! Just curious — was there a particular reason you chose that time?"
   - "Makes sense. Is this something that's generally a priority for you?"
   - "Interesting choice! Would you usually handle it that way?"
4. NEVER explicitly ask about "values." Frame questions around preferences,
   priorities, and habits.
5. When presenting new emails/requests, summarize the key details and
   highlight any conflicts with existing calendar items.
6. Keep track of what the user has already told you and don't repeat questions.

RESPONSE FORMAT:
- For scheduling actions, you may suggest calendar changes using a structured
  card format.
- For conversational replies, just respond naturally.
- If you detect a clear scheduling conflict, present it explicitly.

You are NOT trying to elicit values directly. You are a genuinely helpful
scheduling assistant. The value information emerges from the user's natural
scheduling behavior and the brief rationale questions you ask."""

    async def respond(
        self,
        user_message: str,
        session: Session,
    ) -> dict:
        """Generate a response to a user message.

        Returns:
            dict with keys:
              - text: str (the assistant's message)
              - card: dict | None (structured meeting card if proposing a change)
              - signals: list[ConversationalSignal] (logged signals)
        """
        # Build context from session state
        context = self._build_context(session)
        messages = self._build_messages(session, user_message)

        system = f"""{self.system_prompt}

CURRENT SESSION CONTEXT:
{context}"""

        response_text = await self.call_llm(
            messages=messages,
            system=system,
            temperature=0.7,
        )

        # Log conversational signals
        signals = [
            ConversationalSignal(
                round_num=session.current_round,
                role="user",
                content=user_message,
                signal_type="chat",
            ),
            ConversationalSignal(
                round_num=session.current_round,
                role="assistant",
                content=response_text,
                signal_type="chat",
            ),
        ]

        # Check if the response contains a scheduling suggestion
        card = self._extract_card(response_text)

        return {
            "text": self._clean_response(response_text),
            "card": card,
            "signals": signals,
        }

    async def present_scenario(
        self,
        session: Session,
        emails: list[EmailMessage],
        new_events: list[CalendarEvent],
    ) -> dict:
        """Present a new round's scenario to the participant."""
        email_descriptions = []
        for email in emails:
            email_descriptions.append(
                f"From: {email.sender}\n"
                f"Subject: {email.subject}\n"
                f"{email.body}"
            )

        conflicts = self._detect_conflicts(new_events, session.calendar_events)

        prompt = f"""You just received the following email(s):

{chr(10).join(email_descriptions)}

{f"NOTE: This creates conflicts with existing calendar items: {json.dumps(conflicts)}" if conflicts else ""}

Present these to the user naturally. Summarize the requests, highlight
any scheduling conflicts, and ask what they'd like to do. Be concise
— 2-3 sentences max, then list the key decision points."""

        messages = self._build_messages(session, prompt, is_system_prompt=True)
        response_text = await self.call_llm(
            messages=messages,
            system=self.system_prompt,
            temperature=0.7,
        )

        return {
            "text": self._clean_response(response_text),
            "card": None,
            "emails": [e.model_dump() for e in emails],
        }

    def _build_context(self, session: Session) -> str:
        """Build context string from current session state."""
        events = [
            {"title": e.title, "day": e.day_index, "time": f"{e.start}-{e.end}", "category": e.category}
            for e in session.calendar_events
        ]
        ledger = session.value_ledger.to_summary()
        round_obj = session.current_round_obj()

        parts = [
            f"Round: {session.current_round}/15 ({session.get_phase().value} phase)",
            f"Calendar events: {json.dumps(events)}",
        ]
        if ledger:
            # Don't show value info to the assistant — it should be naive
            # Actually, the assistant needs some awareness to ask good follow-ups
            parts.append(f"Emerging patterns (for context, don't mention directly): {json.dumps(ledger[:3])}")
        if round_obj and round_obj.scenario:
            parts.append(f"Current scenario tensions: {round_obj.scenario.intended_tensions}")

        return "\n".join(parts)

    def _build_messages(
        self,
        session: Session,
        new_message: str,
        is_system_prompt: bool = False,
    ) -> list[dict]:
        """Build the message history for the LLM call."""
        messages = []
        # Include recent chat history for context (last 10 turns)
        recent = session.chat_history[-10:]
        for msg in recent:
            messages.append({"role": msg["role"], "content": msg["content"]})

        if is_system_prompt:
            # This is an internal system action, not a user message
            messages.append({"role": "user", "content": f"[SYSTEM NOTE — present this to me naturally]: {new_message}"})
        else:
            messages.append({"role": "user", "content": new_message})

        return messages

    def _detect_conflicts(
        self,
        new_events: list[CalendarEvent],
        existing_events: list[CalendarEvent],
    ) -> list[dict]:
        """Detect time conflicts between new and existing events."""
        conflicts = []
        for new in new_events:
            for existing in existing_events:
                if new.day_index != existing.day_index:
                    continue
                new_start = self._to_minutes(new.start)
                new_end = self._to_minutes(new.end)
                ex_start = self._to_minutes(existing.start)
                ex_end = self._to_minutes(existing.end)
                if new_start < ex_end and new_end > ex_start:
                    conflicts.append({
                        "new_event": new.title,
                        "conflicts_with": existing.title,
                        "overlap": f"{max(new_start, ex_start)//60}:{max(new_start, ex_start)%60:02d}-"
                                   f"{min(new_end, ex_end)//60}:{min(new_end, ex_end)%60:02d}",
                    })
        return conflicts

    @staticmethod
    def _to_minutes(time_str: str) -> int:
        h, m = time_str.split(":")
        return int(h) * 60 + int(m)

    @staticmethod
    def _clean_response(text: str) -> str:
        """Remove any JSON blocks or system artifacts from the response."""
        lines = text.split("\n")
        cleaned = []
        in_json = False
        for line in lines:
            if line.strip().startswith("```"):
                in_json = not in_json
                continue
            if not in_json:
                cleaned.append(line)
        return "\n".join(cleaned).strip()

    @staticmethod
    def _extract_card(response: str) -> dict | None:
        """Extract a meeting card suggestion if present in the response."""
        # For now, return None — cards are generated explicitly
        # via calendar actions, not embedded in text responses
        return None
