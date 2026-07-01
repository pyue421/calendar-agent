"""Conflict Architect — experimental infrastructure (lab-only).

Generates adaptive scheduling scenarios that surface value-diagnostic
dilemmas. This is NOT a core system agent; it replaces the role of
real incoming requests in a controlled study setting. In deployment,
a lightweight Conflict Recognizer would flag naturally occurring
value-diagnostic moments instead.

Scenario generation adapts across three phases:
  - Exploration (1-5):   Broad scenarios to surface initial value signals
  - Probing (6-10):      Targeted scenarios probing emerging hypotheses
  - Stress Testing (11-15): Forced trade-offs pitting inferred values
                             against each other
"""

from __future__ import annotations

import json

from agents import BaseAgent
from models import (
    CalendarEvent,
    EmailMessage,
    Phase,
    SchedulingScenario,
    Session,
)


class ConflictArchitect(BaseAgent):
    role = "conflict_architect"

    system_prompt = """\
You are the Conflict Architect for the DISCOVER value elicitation study.
Your job is to generate realistic scheduling scenarios that create
value-diagnostic dilemmas for a working adult.

You generate simulated emails and calendar events that force the
participant to make scheduling trade-offs revealing their underlying values.

IMPORTANT PRINCIPLES:
- Scenarios must feel realistic — the kind of requests a working professional receives
- Each scenario should create genuine tension between at least 2 value dimensions
- Never make the "right" answer obvious; both options should be reasonable
- Adapt difficulty and targeting based on the current phase and existing evidence
- Include enough context in emails so the participant can make an informed decision

VALUE DIMENSIONS TO PROBE (not exhaustive):
- Work-life boundaries vs. career ambition
- Personal health vs. social obligations
- Family time vs. professional growth
- Efficiency vs. thoroughness
- Autonomy vs. collaboration
- Punctuality/reliability vs. flexibility
- Financial prudence vs. experiential richness
- Loyalty/commitment vs. self-interest
- Environmental responsibility vs. convenience
- Novelty/growth vs. comfort/routine

Always respond with valid JSON only. No markdown, no commentary."""

    async def generate_scenario(
        self,
        session: Session,
        round_num: int,
    ) -> SchedulingScenario:
        """Generate a scheduling scenario for the given round."""
        phase = session.get_phase(round_num)
        existing_events = [e.model_dump() for e in session.calendar_events]
        ledger_summary = session.value_ledger.to_summary()

        # Build the prompt based on phase
        if phase == Phase.EXPLORATION:
            phase_instructions = self._exploration_prompt()
        elif phase == Phase.PROBING:
            phase_instructions = self._probing_prompt(ledger_summary)
        else:
            phase_instructions = self._stress_test_prompt(ledger_summary)

        prompt = f"""Generate a scheduling scenario for Round {round_num}/15 ({phase.value} phase).

{phase_instructions}

CURRENT CALENDAR STATE:
{json.dumps(existing_events, indent=2)}

CURRENT VALUE HYPOTHESES:
{json.dumps(ledger_summary, indent=2) if ledger_summary else "No hypotheses yet (early exploration)."}

Generate exactly 1-2 emails with scheduling requests that create value tensions.
Each email should propose or imply a calendar event that conflicts with existing
commitments or creates a meaningful trade-off.

Respond with this exact JSON structure:
{{
  "emails": [
    {{
      "sender": "Name <email>",
      "subject": "Email subject",
      "body": "Full email body (2-4 sentences, professional tone)",
      "proposed_event": {{
        "title": "Event title",
        "day_index": 0,
        "start": "HH:MM",
        "end": "HH:MM",
        "category": "work|personal|health|social|obligation",
        "description": "Brief description"
      }},
      "value_tensions": ["value1 vs value2", ...]
    }}
  ],
  "intended_tensions": ["Overall tension 1", "Overall tension 2"],
  "difficulty": "easy|moderate|hard",
  "targeting_rationale": "Why this scenario was chosen given current evidence"
}}"""

        data = await self.call_llm_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )

        # Parse into models
        emails = []
        injected_events = []
        for email_data in data.get("emails", []):
            proposed = email_data.get("proposed_event")
            proposed_event = None
            if proposed:
                proposed_event = CalendarEvent(
                    title=proposed.get("title", "New Event"),
                    day_index=proposed.get("day_index", 0),
                    start=proposed.get("start", "09:00"),
                    end=proposed.get("end", "10:00"),
                    category=proposed.get("category", "work"),
                    description=proposed.get("description", ""),
                    source="conflict_architect",
                    is_new=True,
                    tone=self._tone_for_category(proposed.get("category", "work")),
                )
                injected_events.append(proposed_event)

            emails.append(EmailMessage(
                sender=email_data.get("sender", "Unknown"),
                subject=email_data.get("subject", "Request"),
                body=email_data.get("body", ""),
                proposed_event=proposed_event,
                value_tensions=email_data.get("value_tensions", []),
                round_num=round_num,
            ))

        return SchedulingScenario(
            round_num=round_num,
            phase=phase,
            emails=emails,
            injected_events=injected_events,
            intended_tensions=data.get("intended_tensions", []),
            difficulty=data.get("difficulty", "moderate"),
            targeting_rationale=data.get("targeting_rationale", ""),
        )

    def _exploration_prompt(self) -> str:
        return """EXPLORATION PHASE INSTRUCTIONS:
- Generate broad, diverse scenarios that span different life domains
- Aim to surface initial value signals across multiple dimensions
- Keep difficulty moderate — don't overwhelm, just reveal
- Cover different categories: work meetings, personal commitments,
  health appointments, social events, family obligations
- Example tensions: "urgent work deadline vs. friend's birthday dinner",
  "team meeting vs. personal doctor appointment"
"""

    def _probing_prompt(self, ledger: list[dict]) -> str:
        if not ledger:
            return self._exploration_prompt()

        # Find hypotheses with moderate confidence to probe deeper
        uncertain = [h for h in ledger if 0.3 <= h["confidence"] <= 0.7]
        target_values = [h["value"] for h in uncertain] if uncertain else [h["value"] for h in ledger[:3]]

        return f"""PROBING PHASE INSTRUCTIONS:
- Target scenarios that test specific emerging value hypotheses
- VALUES TO PROBE: {', '.join(target_values)}
- Create scenarios that would either strengthen or weaken these hypotheses
- Increase nuance — the trade-offs should be subtler than exploration phase
- Probe for consistency: does the participant behave the same when the
  stakes change or the context shifts?
- Example: if "work-life boundaries" is a hypothesis, create a scenario
  where a high-status colleague asks for evening help on something
  genuinely important
"""

    def _stress_test_prompt(self, ledger: list[dict]) -> str:
        if not ledger:
            return self._probing_prompt(ledger)

        # Find the strongest hypotheses and pit them against each other
        strong = sorted(ledger, key=lambda h: h["confidence"], reverse=True)[:4]
        pairs = []
        for i, h1 in enumerate(strong):
            for h2 in strong[i + 1:]:
                pairs.append(f"{h1['value']} vs. {h2['value']}")

        return f"""STRESS TESTING PHASE INSTRUCTIONS:
- Create FORCED TRADE-OFFS between the participant's strongest values
- The goal is to reveal the participant's value HIERARCHY, not just
  which values they hold
- VALUE PAIRS TO PIT AGAINST EACH OTHER: {'; '.join(pairs[:3])}
- Make scenarios where both options are genuinely costly — there is
  no free lunch
- Difficulty should be HIGH — these are the rounds that discriminate
  between value profiles
- Example: if both "family time" and "career growth" are strong,
  create a scenario where a career-defining opportunity directly
  conflicts with a family commitment
"""

    @staticmethod
    def _tone_for_category(category: str) -> str:
        return {
            "work": "purple",
            "personal": "blue",
            "health": "green",
            "social": "amber",
            "obligation": "rose",
        }.get(category, "blue")
