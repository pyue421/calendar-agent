"""Replay one exported session under several symmetric Dirichlet priors."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import CONFIG  # noqa: E402
from app.services.bayesian_value_model import GridBayesianValueModel, VALUE_IDS  # noqa: E402


ALPHAS = (0.5, 1.0, 2.0, 5.0)


def replay(exported: dict, alpha: float) -> np.ndarray:
    settings = exported.get("model_config", {})
    config = replace(CONFIG, grid_step=float(settings.get("grid_step", CONFIG.grid_step)),
                     beta=float(settings.get("beta", CONFIG.beta)), prior_alpha=alpha,
                     rationale_reliability=float(settings.get("rationale_reliability", CONFIG.rationale_reliability)))
    model = GridBayesianValueModel(config)
    rationales = {item["decision_id"]: item for item in exported.get("rationales", [])}
    for decision in exported.get("decisions", []):
        model.observe_action(decision["action"], decision["action_features"])
        rationale = rationales.get(decision["decision_id"])
        if rationale:
            observation = rationale["structured_observation"]
            model.observe_values(observation["explicit_value_references"] + observation["implicit_value_references"])
    return model.means()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    exported = json.loads(args.export.read_text(encoding="utf-8"))
    results = {alpha: replay(exported, alpha) for alpha in ALPHAS}
    reference = results[1.0]
    print("alpha\t" + "\t".join(VALUE_IDS) + "\tmax_abs_vs_alpha1\tL1_vs_alpha1")
    for alpha, means in results.items():
        difference = np.abs(means - reference)
        print(f"{alpha:.1f}\t" + "\t".join(f"{value:.6f}" for value in means) +
              f"\t{difference.max():.6f}\t{difference.sum():.6f}")


if __name__ == "__main__":
    main()
