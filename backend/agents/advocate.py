"""Advocate — argues FOR current value hypotheses.

Builds the strongest case that the inferred values are correct,
drawing on accumulated behavioral evidence. Part of the
Advocate-Challenger-Synthesizer debate mechanism that addresses
LLM confirmation bias.
"""

from __future__ import annotations

import json

from agents import BaseAgent
from models import Session


class Advocate(BaseAgent):
    role = "advocate"

    system_prompt = """\
You are the Advocate in the DISCOVER value inference system.
Your role is to argue FOR the current value hypotheses, building
the strongest possible case that these inferred values accurately
represent the participant's true values.

GUIDELINES:
1. Ground every argument in SPECIFIC behavioral evidence from the session.
   Cite exact actions: "In round 3, the user declined a team dinner to
   keep their evening gym slot."
2. Use the Ladder of Abstraction to build inferential chains:
   raw action → behavioral pattern → scheduling priority → abstract value
3. Look for CONSISTENCY across rounds — repeated patterns are stronger
   evidence than one-off actions.
4. Identify convergent evidence — when multiple different actions all
   point to the same underlying value.
5. Be rigorous but genuinely advocate — you believe these hypotheses
   are correct and argue accordingly.

Respond with valid JSON only:
{
  "arguments": [
    {
      "hypothesis_id": "val_xxx",
      "value_label": "...",
      "argument": "Your case for why this value is accurately inferred",
      "key_evidence": ["evidence description 1", "evidence description 2"],
      "confidence_recommendation": 0.0-1.0,
      "ladder": {
        "raw_action": "...",
        "behavioral_pattern": "...",
        "scheduling_priority": "...",
        "abstract_value": "..."
      }
    }
  ],
  "new_hypotheses": [
    {
      "label": "...",
      "description": "...",
      "argument": "Why this new value should be added",
      "evidence": ["..."],
      "initial_confidence": 0.0-1.0,
      "ladder": { ... }
    }
  ]
}"""

    async def argue(self, session: Session) -> dict:
        """Build the case FOR current value hypotheses."""
        behavioral = [
            {
                "round": s.round_num,
                "action": s.action,
                "event": s.event_title,
                "details": s.details,
            }
            for s in session.get_all_behavioral_signals()
        ]
        conversational = [
            {
                "round": s.round_num,
                "role": s.role,
                "content": s.content,
            }
            for s in session.get_all_conversational_signals()
            if s.signal_type == "chat"
        ]
        ledger = session.value_ledger.to_summary()

        prompt = f"""Analyze the following evidence and argue FOR the current value hypotheses.

CURRENT VALUE HYPOTHESES:
{json.dumps(ledger, indent=2) if ledger else "None yet — propose initial hypotheses based on evidence."}

BEHAVIORAL SIGNALS (all rounds so far):
{json.dumps(behavioral, indent=2)}

CONVERSATIONAL SIGNALS (key exchanges):
{json.dumps(conversational[-20:], indent=2)}

Current round: {session.current_round}/15 ({session.get_phase().value} phase)

Build the strongest case you can. If there are no hypotheses yet,
propose new ones based on the evidence. Ground everything in specific actions."""

        return await self.call_llm_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
