from __future__ import annotations

"""Canonical policy head surface with compat alias submodules."""

class ConstraintHead:
    def apply(self, action_payload: dict, constraints: dict) -> dict:
        payload = dict(action_payload)
        for key, value in constraints.items():
            payload.setdefault(key, value)
        return payload

class ContinuousActionHead:
    def choose_action(self, values):
        return tuple(values)

    select = choose_action

class DiscreteActionHead:
    def choose_action(self, logits):
        if not logits:
            raise ValueError("Empty logits")
        return max(range(len(logits)), key=lambda i: logits[i])

    select = choose_action

class DistributionHead:
    def probabilities(self, logits):
        total = sum(logits) if logits else 0.0
        if total == 0:
            return [0.0 for _ in logits]
        return [float(x) / total for x in logits]

class HybridActionHead:
    def choose_action(self, discrete, continuous):
        return {"discrete": discrete, "continuous": tuple(continuous)}

    select = choose_action

class QValueHead:
    def values(self, action_values):
        return list(action_values)

class TemperatureHead:
    def apply(self, logits, temperature: float):
        if temperature <= 0:
            raise ValueError("temperature must be positive")
        return [x / temperature for x in logits]

class UncertaintyHead:
    def estimate(self, scores):
        if not scores:
            return 0.0
        mean = sum(scores) / len(scores)
        return sum((x - mean) ** 2 for x in scores) / len(scores)

class ValueHead:
    def value(self, features):
        return float(sum(features) if features else 0.0)

_ALIAS_EXPORTS = {
    "constraint_head": "ConstraintHead",
    "continuous_action_head": "ContinuousActionHead",
    "discrete_action_head": "DiscreteActionHead",
    "distribution_head": "DistributionHead",
    "hybrid_action_head": "HybridActionHead",
    "q_value_head": "QValueHead",
    "temperature_head": "TemperatureHead",
    "uncertainty_head": "UncertaintyHead",
    "value_head": "ValueHead",
}

__all__ = [
    "ConstraintHead",
    "ContinuousActionHead",
    "DiscreteActionHead",
    "DistributionHead",
    "HybridActionHead",
    "QValueHead",
    "TemperatureHead",
    "UncertaintyHead",
    "ValueHead",
] + list(_ALIAS_EXPORTS)
