"""Synthesizer / Reflection Facilitator.

Takes the Advocate-Challenger debate output and produces a balanced
synthesis. At reflection touchpoints (rounds 5, 10, 15), facilitates
the participant's reflection, grounding every prompt in specific
behavioral evidence rather than abstract questioning.
"""

from __future__ import annotations

import json

from agents import BaseAgent
from models import (
    DebateRecord,
    Evidence,
    AbstractionLevel,
    Session,
    ValueHypothesis,
)


class Synthesizer(BaseAgent):
    role = "synthesizer"

    system_prompt = """\
You are the Synthesizer in the DISCOVER value inference system.
You receive arguments from the Advocate (FOR current hypotheses) and
the Challenger (AGAINST them), and produce a balanced synthesis that
updates the value model.

GUIDELINES:
1. Weigh evidence quality, not just quantity. One strong behavioral
   signal can outweigh several weak conversational ones.
2. Update confidence scores based on the strength of arguments from
   both sides.
3. When the Challenger offers a compelling alternative explanation,
   either lower confidence or split the hypothesis.
4. When the Advocate shows strong convergent evidence, increase confidence.
5. Propose MERGING hypotheses that are too similar, and SPLITTING
   hypotheses that conflate distinct values.
6. Track the Ladder of Abstraction for each hypothesis — ensure every
   abstract value is grounded in concrete behavioral evidence.

Respond with valid JSON only."""

    async def synthesize(
        self,
        session: Session,
        advocate_output: dict,
        challenger_output: dict,
    ) -> dict:
        """Synthesize the Advocate-Challenger debate into ledger updates."""

        prompt = f"""Synthesize the following debate about the participant's values.

ADVOCATE'S ARGUMENTS (FOR):
{json.dumps(advocate_output, indent=2)}

CHALLENGER'S ARGUMENTS (AGAINST):
{json.dumps(challenger_output, indent=2)}

CURRENT VALUE HYPOTHESES:
{json.dumps(session.value_ledger.to_summary(), indent=2)}

Round: {session.current_round}/15

Produce a balanced synthesis. For each hypothesis, decide:
- Should confidence go UP, DOWN, or STAY?
- Should the hypothesis be KEPT, MODIFIED, MERGED, or DROPPED?
- Are there NEW hypotheses to add?

Respond with:
{{
  "synthesis_narrative": "Brief narrative of the deliberation outcome",
  "hypothesis_updates": [
    {{
      "hypothesis_id": "val_xxx (or 'new' for new hypotheses)",
      "label": "...",
      "description": "...",
      "action": "keep|modify|merge|drop|new",
      "new_confidence": 0.0-1.0,
      "rationale": "Why this update",
      "new_evidence": [
        {{
          "description": "What happened",
          "source_type": "behavioral|conversational",
          "supports": true,
          "strength": 0.0-1.0,
          "abstraction_level": "raw_action|behavioral_pattern|scheduling_priority|abstract_value"
        }}
      ],
      "ladder": {{
        "raw_action": "...",
        "behavioral_pattern": "...",
        "scheduling_priority": "...",
        "abstract_value": "..."
      }}
    }}
  ]
}}"""

        return await self.call_llm_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

    async def generate_reflection(
        self,
        session: Session,
        round_num: int,
    ) -> str:
        """Generate a reflection prompt for touchpoint rounds (5, 10, 15).

        The reflection is grounded in SPECIFIC behavioral evidence,
        not abstract value questioning.
        """
        ledger = session.value_ledger.to_summary()
        behavioral = [
            {
                "round": s.round_num,
                "action": s.action,
                "event": s.event_title,
                "details": s.details,
            }
            for s in session.get_all_behavioral_signals()
        ]

        if round_num == 5:
            phase_context = "This is the first reflection point. Focus on emerging patterns."
        elif round_num == 10:
            phase_context = (
                "This is the mid-session reflection. The participant has been through "
                "probing scenarios. Focus on what's become clearer and what's still uncertain."
            )
        else:
            phase_context = (
                "This is the FINAL reflection. The participant has been through stress tests. "
                "Focus on the value hierarchy that has emerged and any surprising discoveries."
            )

        prompt = f"""Generate a reflection prompt for the participant at Round {round_num}/15.

{phase_context}

CURRENT VALUE HYPOTHESES:
{json.dumps(ledger, indent=2)}

KEY BEHAVIORAL EVIDENCE:
{json.dumps(behavioral[-10:], indent=2)}

CRITICAL RULES FOR REFLECTION PROMPTS:
1. Ground EVERY observation in a SPECIFIC action the participant took.
   "I noticed you moved the team dinner to keep your evening run" — not
   "It seems like health is important to you."
2. Use the participant's own words when possible (from conversational signals).
3. Frame observations as questions, not conclusions:
   "I noticed X happened — does that resonate with how you think about
   this kind of choice?" rather than "You clearly value X."
4. If round 15: highlight SURPRISES — patterns the participant might not
   have noticed about their own behavior.
5. Keep it conversational, warm, and under 150 words.
6. Ask ONE focused question, not a barrage.

Write the reflection prompt directly — no JSON wrapping, just the text
the participant will see."""

        return await self.call_llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )

    def apply_synthesis(
        self,
        session: Session,
        synthesis: dict,
        advocate_output: dict,
        challenger_output: dict,
    ) -> DebateRecord:
        """Apply synthesis results to the session's Value Evidence Ledger."""
        updated_ids = []
        new_ids = []

        for update in synthesis.get("hypothesis_updates", []):
            action = update.get("action", "keep")

            if action == "new" or update.get("hypothesis_id") == "new":
                # Create new hypothesis
                hyp = ValueHypothesis(
                    label=update.get("label", "Unknown"),
                    description=update.get("description", ""),
                    confidence=update.get("new_confidence", 0.5),
                    first_observed_round=session.current_round,
                    last_updated_round=session.current_round,
                    abstraction_ladder=update.get("ladder", {}),
                )
                # Add evidence
                for ev_data in update.get("new_evidence", []):
                    ev = Evidence(
                        round_num=session.current_round,
                        abstraction_level=AbstractionLevel(
                            ev_data.get("abstraction_level", "raw_action")
                        ),
                        description=ev_data.get("description", ""),
                        source_type=ev_data.get("source_type", "behavioral"),
                        source_id="",
                        supports=ev_data.get("supports", True),
                        strength=ev_data.get("strength", 0.5),
                    )
                    session.value_ledger.evidence.append(ev)
                    hyp.evidence_ids.append(ev.id)

                session.value_ledger.hypotheses.append(hyp)
                new_ids.append(hyp.id)

            elif action == "drop":
                # Remove hypothesis
                session.value_ledger.hypotheses = [
                    h for h in session.value_ledger.hypotheses
                    if h.id != update.get("hypothesis_id")
                ]

            elif action in ("keep", "modify", "merge"):
                # Update existing hypothesis
                hyp = session.value_ledger.get_hypothesis(update.get("hypothesis_id", ""))
                if not hyp:
                    # Try to find by label
                    hyp = next(
                        (h for h in session.value_ledger.hypotheses
                         if h.label == update.get("label")),
                        None,
                    )
                if hyp:
                    if action == "modify" and update.get("label"):
                        hyp.label = update["label"]
                    if update.get("description"):
                        hyp.description = update["description"]
                    hyp.confidence = update.get("new_confidence", hyp.confidence)
                    hyp.last_updated_round = session.current_round
                    if update.get("ladder"):
                        hyp.abstraction_ladder = update["ladder"]

                    # Add new evidence
                    for ev_data in update.get("new_evidence", []):
                        ev = Evidence(
                            round_num=session.current_round,
                            abstraction_level=AbstractionLevel(
                                ev_data.get("abstraction_level", "raw_action")
                            ),
                            description=ev_data.get("description", ""),
                            source_type=ev_data.get("source_type", "behavioral"),
                            source_id="",
                            supports=ev_data.get("supports", True),
                            strength=ev_data.get("strength", 0.5),
                        )
                        session.value_ledger.evidence.append(ev)
                        hyp.evidence_ids.append(ev.id)

                    updated_ids.append(hyp.id)

        return DebateRecord(
            round_num=session.current_round,
            advocate_argument=json.dumps(advocate_output),
            challenger_argument=json.dumps(challenger_output),
            synthesis=synthesis.get("synthesis_narrative", ""),
            updated_hypotheses=updated_ids,
            new_hypotheses=new_ids,
        )
