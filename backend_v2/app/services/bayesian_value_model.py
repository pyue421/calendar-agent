from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass

from ..config import ModelConfig


VALUE_IDS = (
    "wellbeing", "achievement", "reliability", "relationships", "autonomy",
    "collaboration", "fairness", "growth", "privacy", "community_contribution",
    "boundaries", "security",
)

VALUE_LABELS = {
    "wellbeing": "Wellbeing", "achievement": "Achievement", "reliability": "Reliability",
    "relationships": "Relationships", "autonomy": "Autonomy", "collaboration": "Collaboration",
    "fairness": "Fairness", "growth": "Growth", "privacy": "Privacy",
    "community_contribution": "Community", "boundaries": "Boundaries", "security": "Security",
}


@dataclass
class ParticleState:
    particles: list[list[float]]
    weights: list[float]


class BayesianValueModel:
    def __init__(self, config: ModelConfig, state: ParticleState | None = None):
        self.config = config
        if state:
            self.state = copy.deepcopy(state)
        else:
            rng = random.Random(config.seed)
            particles = []
            for _ in range(config.particle_count):
                draws = [rng.expovariate(1.0) for _ in VALUE_IDS]
                total = sum(draws)
                particles.append([x / total for x in draws])
            self.state = ParticleState(particles, [1 / config.particle_count] * config.particle_count)
        self._rng = random.Random(config.seed + 1)

    def clone(self) -> "BayesianValueModel":
        return BayesianValueModel(self.config, self.state)

    def observe_action(self, chosen: str, action_features: dict[str, list[float]]) -> None:
        names = list(action_features)
        if chosen not in action_features:
            raise ValueError(f"Unknown candidate action: {chosen}")
        likelihoods = []
        for particle in self.state.particles:
            logits = [self.config.beta * sum(w * f for w, f in zip(particle, action_features[a])) for a in names]
            peak = max(logits)
            exps = [math.exp(x - peak) for x in logits]
            likelihoods.append(exps[names.index(chosen)] / sum(exps))
        self.state.weights = [w * p for w, p in zip(self.state.weights, likelihoods)]
        self._normalize()
        if self.effective_sample_size() < self.config.particle_count * self.config.resample_ess_ratio:
            self._resample()

    def observe_values(self, value_ids: list[str], reliability: float) -> None:
        indices = [VALUE_IDS.index(v) for v in value_ids if v in VALUE_IDS]
        if not indices:
            return
        baseline = 1 / len(VALUE_IDS)
        factors = []
        for particle in self.state.particles:
            signal = sum(particle[i] for i in indices) / len(indices)
            factors.append((1 - reliability) + reliability * max(signal / baseline, 1e-6))
        self.state.weights = [w * f for w, f in zip(self.state.weights, factors)]
        self._normalize()

    def effective_sample_size(self) -> float:
        return 1 / sum(w * w for w in self.state.weights)

    def _normalize(self) -> None:
        total = sum(self.state.weights)
        if total <= 0:
            self.state.weights = [1 / len(self.state.weights)] * len(self.state.weights)
        else:
            self.state.weights = [w / total for w in self.state.weights]

    def _resample(self) -> None:
        n = len(self.state.particles)
        start = self._rng.random() / n
        points = [start + i / n for i in range(n)]
        cumulative, j, chosen = self.state.weights[0], 0, []
        for point in points:
            while point > cumulative and j < n - 1:
                j += 1
                cumulative += self.state.weights[j]
            chosen.append(self.state.particles[j][:])
        self.state = ParticleState(chosen, [1 / n] * n)

    def summary(self) -> list[dict]:
        result = []
        for i, value_id in enumerate(VALUE_IDS):
            mean = sum(w * p[i] for w, p in zip(self.state.weights, self.state.particles))
            variance = sum(w * (p[i] - mean) ** 2 for w, p in zip(self.state.weights, self.state.particles))
            result.append({
                "id": value_id, "label": VALUE_LABELS[value_id],
                "weight": round(mean * 100, 2), "uncertainty": round(math.sqrt(variance) * 100, 2),
            })
        return result

