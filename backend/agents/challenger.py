"""Challenger — argues AGAINST current value hypotheses.

Actively looks for disconfirming evidence, alternative interpretations,
and under-supported inferences. Exists specifically to counteract LLM
confirmation bias — without it, the system would mirror user input
rather than genuinely probe.
"""

from __future__ import annotations

import json

from agents import BaseAgent
from models import Session


class Challenger(BaseAgent):
    role = "challenger"

    system_prompt = """\
You are the Challenger in the DISCOVER value inference system.
Your role is to CHALLENGE the current value hypotheses, actively
looking for disconfirming evidence, alternative interpretations,
and unsupported inferential leaps.

You exist to counteract confirmation bias. The Advocate will try
to build the strongest case FOR the hypotheses — your job is to
find the weaknesses.

GUIDELINES:
1. Look for ALTERNATIVE EXPLANATIONS for the same behavior.
   "They declined the evening meeting" could mean work-life boundaries,
   OR they simply had a prior commitment, OR they dislike that colleague.
2. Identify INCONSISTENCIES — times when the participant acted contrary
   to the hypothesized value.
3. Challenge the INFERENTIAL LEAP on the Ladder of Abstraction.
   Is the jump from "declined 2 evening meetings" to "values work-life
   boundaries" actually supported, or is it over-interpretation?
4. Flag INSUFFICIENT EVIDENCE — hypotheses supported by only 1-2
   data points should be challenged as premature.
5. Watch for CONFLATION — are two distinct values being collapsed
   into one? Or one value being split unnecessarily?
6. Be genuinely adversarial but constructive. Your goal is accurate
   inference, not destruction.

Respond with valid JSON only:
{
  "challenges": [
    {
      "hypothesis_id": "val_xxx",
      "value_label": "...",
      "challenge": "Your argument against this hypothesis",
      "alternative_explanations": ["..."],
      "disconfirming_evidence": ["..."],
      "inferential_weaknesses": ["..."],
      "confidence_recommendation": 0.0-1.0
    }
  ],
  "overarching_concerns": [
    "Broad concern about the current hypothesis set, e.g., missing dimensions"
  ]
}"""

    async def challenge(self, session: Session) -> dict:
        """Build the case AGAINST current value hypotheses."""
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

        prompt = f"""Challenge the following value hypotheses. Find weaknesses,
alternative explanations, and disconfirming evidence.

CURRENT VALUE HYPOTHESES:
{json.dumps(ledger, indent=2) if ledger else "No hypotheses to challenge yet."}

BEHAVIORAL SIGNALS (all rounds so far):
{json.dumps(behavioral, indent=2)}

CONVERSATIONAL SIGNALS (key exchanges):
{json.dumps(conversational[-20:], indent=2)}

Current round: {session.current_round}/15 ({session.get_phase().value} phase)

Be rigorous. Every hypothesis should be scrutinized. Look for:
- Behaviors that CONTRADICT the hypothesized value
- Alternative explanations for observed patterns
- Inferential leaps that aren't sufficiently supported
- Value dimensions that the current set is MISSING"""

        return await self.call_llm_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )
