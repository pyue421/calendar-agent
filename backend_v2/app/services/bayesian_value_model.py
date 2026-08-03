from __future__ import annotations

from functools import lru_cache
from itertools import combinations

import numpy as np

from ..config import ModelConfig
from .value_taxonomy import VALUE_BY_ID, VALUE_IDS



@lru_cache(maxsize=8)
def simplex_grid(step: float, dimensions: int = 5) -> np.ndarray:
    units = round(1.0 / step)
    if not np.isclose(units * step, 1.0) or units < 1:
        raise ValueError("grid_step must divide 1.0 exactly")
    rows = []
    for bars in combinations(range(units + dimensions - 1), dimensions - 1):
        stops = (-1, *bars, units + dimensions - 1)
        rows.append([(stops[i + 1] - stops[i] - 1) / units for i in range(dimensions)])
    grid = np.asarray(rows, dtype=np.float64)
    grid.setflags(write=False)
    return grid


def weighted_quantile(values: np.ndarray, probabilities: np.ndarray, quantile: float) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(probabilities[order])
    return float(values[order[min(np.searchsorted(cumulative, quantile, side="left"), len(order) - 1)]])


class GridBayesianValueModel:
    """Deterministic Bayesian posterior over a five-dimensional simplex grid."""
    def __init__(self, config: ModelConfig, posterior: np.ndarray | None = None):
        if config.prior_family != "symmetric_dirichlet" or config.prior_alpha <= 0:
            raise ValueError("Use a positive symmetric_dirichlet prior")
        self.config = config
        self.grid = simplex_grid(config.grid_step, len(VALUE_IDS))
        self.posterior = posterior.copy() if posterior is not None else self._prior()

    def _prior(self) -> np.ndarray:
        if self.config.prior_alpha == 1.0:
            return np.full(len(self.grid), 1.0 / len(self.grid))
        safe = np.maximum(self.grid, self.config.grid_step / 2)
        log_density = (self.config.prior_alpha - 1.0) * np.log(safe).sum(axis=1)
        log_density -= log_density.max()
        density = np.exp(log_density)
        return density / density.sum()

    def clone(self) -> "GridBayesianValueModel":
        return GridBayesianValueModel(self.config, self.posterior)

    def observe_action(self, chosen: str, action_features: dict[str, list[float]]) -> None:
        names = list(action_features)
        if chosen not in names:
            raise ValueError(f"Unknown candidate action: {chosen}")
        matrix = np.asarray([action_features[name] for name in names], dtype=np.float64)
        if matrix.shape[1] != len(VALUE_IDS):
            raise ValueError("Action features must match the five-dimensional vocabulary")
        logits = self.config.beta * self.grid @ matrix.T
        logits -= logits.max(axis=1, keepdims=True)
        exp_logits = np.exp(logits)
        self._apply_likelihood(exp_logits[:, names.index(chosen)] / exp_logits.sum(axis=1))

    def observe_values(self, value_ids: list[str], reliability: float | None = None) -> None:
        indices = sorted({VALUE_IDS.index(v) for v in value_ids if v in VALUE_IDS})
        if not indices:
            return
        r = self.config.rationale_reliability if reliability is None else reliability
        if not 0 <= r <= 1:
            raise ValueError("Rationale reliability must be between 0 and 1")
        signal = self.grid[:, indices].mean(axis=1)
        likelihood = (1.0 - r) + r * np.maximum(signal / (1.0 / len(VALUE_IDS)), 1e-12)
        self._apply_likelihood(likelihood)

    def _apply_likelihood(self, likelihood: np.ndarray) -> None:
        updated = self.posterior * likelihood
        total = float(updated.sum())
        if not np.isfinite(total) or total <= 0:
            raise ValueError("Posterior normalization failed")
        self.posterior = updated / total

    def means(self) -> np.ndarray:
        return self.posterior @ self.grid

    def summary(self) -> list[dict]:
        means = self.means()
        result = []
        for i, value_id in enumerate(VALUE_IDS):
            variance = float(self.posterior @ ((self.grid[:, i] - means[i]) ** 2))
            relative = float(means[i] * 100)
            definition = VALUE_BY_ID[value_id]
            result.append({"id": value_id, "label": definition["label"], "tone": definition["tone"],
                           "description": definition["description"], "posterior_mean": round(float(means[i]), 6),
                           "relative_weight": round(relative, 2), "weight": round(relative, 2),
                           "posterior_std": round(variance ** 0.5, 6), "uncertainty": round(variance ** 0.5 * 100, 2),
                           "credible_interval_90": {"lower": round(weighted_quantile(self.grid[:, i], self.posterior, 0.05), 6),
                                                    "upper": round(weighted_quantile(self.grid[:, i], self.posterior, 0.95), 6)}})
        return result


BayesianValueModel = GridBayesianValueModel
