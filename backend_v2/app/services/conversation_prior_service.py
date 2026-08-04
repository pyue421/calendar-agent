from __future__ import annotations

import numpy as np

from ..config import OnboardingConfig
from .value_taxonomy import VALUE_IDS

RELATION = {"supports": 1.0, "challenges": -1.0}
DIRECTNESS = {"explicit": 1.0, "implicit": 0.6, "ambiguous": 0.25}
STRENGTH = {"weak": 0.5, "moderate": 1.0, "strong": 1.5}
REVIEW = {"accepted": 1.0, "ambiguous": 0.35, "rejected": 0.0}
ALGORITHM_VERSION = "conversation_prior_builder_v1"


def build_conversation_prior(model, reviewed_evidence: list[dict], config: OnboardingConfig) -> dict:
    scores = {value_id: 0.0 for value_id in VALUE_IDS}
    for item in reviewed_evidence:
        contribution = (RELATION[item["relation"]] * DIRECTNESS[item["directness"]] *
                        STRENGTH[item["strength"]] * REVIEW[item["review_status"]])
        scores[item["value_id"]] += contribution
        item["deterministic_contribution"] = contribution
    clipped = {key: float(np.clip(value, -config.score_clip, config.score_clip)) for key, value in scores.items()}
    mean = sum(clipped.values()) / len(clipped)
    centered = {key: value - mean for key, value in clipped.items()}
    base = model.base_prior_posterior()
    vector = np.asarray([centered[value_id] for value_id in VALUE_IDS])
    log_likelihood = config.evidence_scale * (model.grid @ vector)
    log_likelihood -= log_likelihood.max()
    evidence = base * np.exp(log_likelihood); evidence /= evidence.sum()
    mixed = (1 - config.mixture_weight) * base + config.mixture_weight * evidence
    mixed /= mixed.sum()
    return {"algorithm_version": ALGORITHM_VERSION, "aggregate_scores": scores, "clipped_scores": clipped,
            "centered_scores": centered, "base_prior": base, "evidence_posterior": evidence,
            "conversation_informed_prior": mixed,
            "prior_parameters": {"evidence_scale": config.evidence_scale, "mixture_weight": config.mixture_weight,
                                 "score_clip": config.score_clip}}
