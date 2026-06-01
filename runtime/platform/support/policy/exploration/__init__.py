from __future__ import annotations

"""Canonical policy exploration surface with compat alias submodules."""

import math
import random


def _boltzmann_choose(scores, temperature: float = 1.0) -> int:
    exps = [math.exp(s / temperature) for s in scores]
    total = sum(exps)
    threshold = random.random() * total
    acc = 0.0
    for idx, value in enumerate(exps):
        acc += value
        if acc >= threshold:
            return idx
    return len(scores) - 1

def _curiosity_bonus(prediction_error: float, scale: float = 1.0) -> float:
    return prediction_error * scale

def _entropy(probabilities) -> float:
    return -sum(p * math.log(p) for p in probabilities if p > 0)

def _epsilon_greedy_choose(best_index: int, action_count: int, epsilon: float) -> int:
    if random.random() < epsilon:
        return random.randrange(action_count)
    return best_index

def _add_noise(values, sigma: float):
    return [v + random.gauss(0.0, sigma) for v in values]

def _perturb(params, sigma: float):
    return [p + random.gauss(0.0, sigma) for p in params]

def _thompson_choose(alpha_beta_pairs):
    sampled = [random.betavariate(alpha, beta) for alpha, beta in alpha_beta_pairs]
    return max(range(len(sampled)), key=lambda i: sampled[i])

def _ucb_choose(values, counts, total_steps: int, c: float = 2.0) -> int:
    scored = []
    for i, value in enumerate(values):
        bonus = c * math.sqrt(math.log(max(total_steps, 1) + 1) / max(counts[i], 1))
        scored.append(value + bonus)
    return max(range(len(scored)), key=lambda i: scored[i])

_MODULE_EXPORTS = {
    "boltzmann": {"choose": f"{__name__}:_boltzmann_choose"},
    "curiosity_bonus": {"bonus": f"{__name__}:_curiosity_bonus"},
    "entropy_regularization": {"entropy": f"{__name__}:_entropy"},
    "epsilon_greedy": {"choose": f"{__name__}:_epsilon_greedy_choose"},
    "noise_injection": {"add_noise": f"{__name__}:_add_noise"},
    "parameter_noise": {"perturb": f"{__name__}:_perturb"},
    "thompson_sampling": {"choose": f"{__name__}:_thompson_choose"},
    "ucb": {"choose": f"{__name__}:_ucb_choose"},
}

__all__ = list(_MODULE_EXPORTS)
