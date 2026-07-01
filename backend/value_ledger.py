"""Value Evidence Ledger — manages the inferential state of DISCOVER.

Provides higher-level operations over the raw ValueEvidenceLedger model:
  - Adding/updating/removing hypotheses with evidence tracking
  - Querying the ledger by confidence, recency, abstraction level
  - Computing uncertainty (variance across recent rounds) for the
    Conflict Architect's targeting
  - Generating profile snapshots for post-hoc signal decomposition
"""

from __future__ import annotations

import statistics
from typing import Literal

from models import (
    AbstractionLevel,
    Evidence,
    ValueEvidenceLedger,
    ValueHypothesis,
)


class LedgerManager:
    """Higher-level operations over a ValueEvidenceLedger."""

    def __init__(self, ledger: ValueEvidenceLedger):
        self.ledger = ledger

    # ── Queries ──────────────────────────────────────────────────────

    def top_hypotheses(self, n: int = 5) -> list[ValueHypothesis]:
        """Return the n highest-confidence hypotheses."""
        return sorted(
            self.ledger.hypotheses,
            key=lambda h: h.confidence,
            reverse=True,
        )[:n]

    def uncertain_hypotheses(
        self,
        min_conf: float = 0.3,
        max_conf: float = 0.7,
    ) -> list[ValueHypothesis]:
        """Return hypotheses in the uncertain confidence band."""
        return [
            h for h in self.ledger.hypotheses
            if min_conf <= h.confidence <= max_conf
        ]

    def hypotheses_by_recency(self, last_n_rounds: int = 3) -> list[ValueHypothesis]:
        """Return hypotheses updated in the last N rounds."""
        if not self.ledger.hypotheses:
            return []
        max_round = max(h.last_updated_round for h in self.ledger.hypotheses)
        cutoff = max_round - last_n_rounds
        return [h for h in self.ledger.hypotheses if h.last_updated_round > cutoff]

    def evidence_for_hypothesis(
        self,
        hypothesis_id: str,
        source_type: str | None = None,
    ) -> list[Evidence]:
        """Get all evidence for a hypothesis, optionally filtered by source type."""
        hyp = self.ledger.get_hypothesis(hypothesis_id)
        if not hyp:
            return []
        evidence = [e for e in self.ledger.evidence if e.id in hyp.evidence_ids]
        if source_type:
            evidence = [e for e in evidence if e.source_type == source_type]
        return evidence

    # ── Uncertainty Targeting ────────────────────────────────────────

    def compute_uncertainty_scores(self, window: int = 3) -> dict[str, float]:
        """Compute uncertainty scores for the Conflict Architect.

        Uses variance in confidence across the last `window` debate rounds
        as the uncertainty signal. High variance means the hypothesis is
        still being actively debated — a good target for stress testing.

        Returns:
            dict mapping hypothesis_id → uncertainty score (0.0-1.0)
        """
        scores = {}
        for hyp in self.ledger.hypotheses:
            # Collect confidence snapshots from evidence rounds
            rounds_seen = set()
            for eid in hyp.evidence_ids:
                ev = next((e for e in self.ledger.evidence if e.id == eid), None)
                if ev:
                    rounds_seen.add(ev.round_num)

            if len(rounds_seen) < 2:
                # Not enough data — assume moderate uncertainty
                scores[hyp.id] = 0.5
                continue

            # Use evidence strength variance as proxy for debate intensity
            recent_evidence = [
                e for e in self.ledger.evidence
                if e.id in hyp.evidence_ids
                and e.round_num >= max(rounds_seen) - window
            ]
            if len(recent_evidence) < 2:
                scores[hyp.id] = 0.5
                continue

            strengths = [e.strength for e in recent_evidence]
            # Mix of supporting/challenging evidence = high uncertainty
            supports = [e for e in recent_evidence if e.supports]
            challenges = [e for e in recent_evidence if not e.supports]
            balance_ratio = min(len(supports), len(challenges)) / max(
                len(supports), len(challenges), 1
            )

            try:
                variance = statistics.variance(strengths)
            except statistics.StatisticsError:
                variance = 0.0

            # Combine variance and balance ratio
            scores[hyp.id] = min(1.0, (variance + balance_ratio) / 2)

        return scores

    def get_targeting_priorities(self, window: int = 3) -> list[dict]:
        """Get prioritized list for the Conflict Architect's scenario generation.

        Returns hypotheses sorted by uncertainty, with context about what
        to probe and why.
        """
        uncertainty = self.compute_uncertainty_scores(window)
        priorities = []
        for hyp in self.ledger.hypotheses:
            u_score = uncertainty.get(hyp.id, 0.5)
            supporting = len([
                e for e in self.ledger.evidence
                if e.id in hyp.evidence_ids and e.supports
            ])
            challenging = len([
                e for e in self.ledger.evidence
                if e.id in hyp.evidence_ids and not e.supports
            ])
            priorities.append({
                "hypothesis_id": hyp.id,
                "value": hyp.label,
                "confidence": hyp.confidence,
                "uncertainty": u_score,
                "supporting_count": supporting,
                "challenging_count": challenging,
                "needs_probing": u_score > 0.4 or abs(supporting - challenging) < 2,
            })
        return sorted(priorities, key=lambda p: p["uncertainty"], reverse=True)

    # ── Mutations ────────────────────────────────────────────────────

    def add_hypothesis(
        self,
        label: str,
        description: str,
        confidence: float,
        round_num: int,
        ladder: dict[str, str] | None = None,
    ) -> ValueHypothesis:
        """Add a new value hypothesis to the ledger."""
        hyp = ValueHypothesis(
            label=label,
            description=description,
            confidence=confidence,
            first_observed_round=round_num,
            last_updated_round=round_num,
            abstraction_ladder=ladder or {},
        )
        self.ledger.hypotheses.append(hyp)
        return hyp

    def add_evidence(
        self,
        hypothesis_id: str,
        round_num: int,
        description: str,
        source_type: Literal["behavioral", "conversational"],
        source_id: str = "",
        supports: bool = True,
        strength: float = 0.5,
        abstraction_level: AbstractionLevel = AbstractionLevel.RAW_ACTION,
    ) -> Evidence | None:
        """Add evidence linked to a hypothesis."""
        hyp = self.ledger.get_hypothesis(hypothesis_id)
        if not hyp:
            return None
        ev = Evidence(
            round_num=round_num,
            abstraction_level=abstraction_level,
            description=description,
            source_type=source_type,
            source_id=source_id,
            supports=supports,
            strength=strength,
        )
        self.ledger.evidence.append(ev)
        hyp.evidence_ids.append(ev.id)
        hyp.last_updated_round = round_num
        return ev

    def update_confidence(self, hypothesis_id: str, new_confidence: float) -> None:
        """Update a hypothesis's confidence score."""
        hyp = self.ledger.get_hypothesis(hypothesis_id)
        if hyp:
            hyp.confidence = max(0.0, min(1.0, new_confidence))

    def remove_hypothesis(self, hypothesis_id: str) -> None:
        """Remove a hypothesis and its associated evidence."""
        self.ledger.hypotheses = [
            h for h in self.ledger.hypotheses if h.id != hypothesis_id
        ]
        # Evidence is kept for audit trail but unlinked

    # ── Post-hoc Signal Decomposition ────────────────────────────────

    def generate_profile(
        self,
        profile_type: Literal["full", "behavioral_only", "conversational_only"],
    ) -> list[dict]:
        """Generate a value profile using only the specified signal type.

        This enables the within-subjects post-hoc decomposition:
          - Profile A: full pipeline (behavioral + conversational)
          - Profile B: conversational signals only
          - Profile C: behavioral signals only

        Returns a summary in the same format as ValueEvidenceLedger.to_summary().
        """
        if profile_type == "full":
            return self.ledger.to_summary()

        # Filter evidence by source type
        allowed_source = (
            "behavioral" if profile_type == "behavioral_only"
            else "conversational"
        )
        filtered_evidence = [
            e for e in self.ledger.evidence if e.source_type == allowed_source
        ]
        filtered_ids = {e.id for e in filtered_evidence}

        result = []
        for hyp in self.ledger.hypotheses:
            relevant_evidence = [
                e for e in filtered_evidence if e.id in hyp.evidence_ids
            ]
            if not relevant_evidence:
                continue  # Skip hypotheses with no evidence of this type

            supporting = [e for e in relevant_evidence if e.supports]
            challenging = [e for e in relevant_evidence if not e.supports]

            # Recompute confidence based only on filtered evidence
            if supporting or challenging:
                avg_strength = (
                    sum(e.strength for e in supporting) - sum(e.strength for e in challenging)
                ) / len(relevant_evidence)
                adjusted_confidence = max(0.0, min(1.0, 0.5 + avg_strength / 2))
            else:
                adjusted_confidence = 0.5

            result.append({
                "value": hyp.label,
                "description": hyp.description,
                "confidence": adjusted_confidence,
                "supporting_evidence_count": len(supporting),
                "challenging_evidence_count": len(challenging),
                "ladder": hyp.abstraction_ladder,
                "first_seen": hyp.first_observed_round,
                "last_updated": hyp.last_updated_round,
            })

        return sorted(result, key=lambda r: r["confidence"], reverse=True)
