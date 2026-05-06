from __future__ import annotations

"""Canonical credit-assignment surface with compat alias submodules."""

def propagate(rewards: list[float], gamma: float = 0.99) -> list[float]:
    running = 0.0
    output: list[float] = []
    for reward in reversed(rewards):
        running = reward + gamma * running
        output.append(running)
    return list(reversed(output))

class EligibilityTraces:
    def __init__(self, lam: float = 0.95) -> None:
        self._lam = lam
        self._trace = 0.0

    def update(self, signal: float) -> float:
        self._trace = signal + self._lam * self._trace
        return self._trace

def gae(
    rewards: list[float],
    values: list[float],
    gamma: float = 0.99,
    lam: float = 0.95,
) -> list[float]:
    advantages = [0.0 for _ in rewards]
    running = 0.0
    next_value = 0.0
    for index in reversed(range(len(rewards))):
        delta = rewards[index] + gamma * next_value - values[index]
        running = delta + gamma * lam * running
        advantages[index] = running
        next_value = values[index]
    return advantages

def returns(rewards: list[float], gamma: float = 0.99) -> list[float]:
    output = [0.0 for _ in rewards]
    running = 0.0
    for index in reversed(range(len(rewards))):
        running = rewards[index] + gamma * running
        output[index] = running
    return output

def assign_sequence_credit(sequence_rewards: list[float]) -> list[float]:
    total = sum(sequence_rewards)
    if not sequence_rewards:
        return []
    share = total / len(sequence_rewards)
    return [share for _ in sequence_rewards]

def td_target(reward: float, next_value: float, gamma: float = 0.99) -> float:
    return reward + gamma * next_value

_ALIAS_EXPORTS = {
    "delayed_credit_propagation": "propagate",
    "eligibility_traces": "EligibilityTraces",
    "generalized_advantage_estimation": "gae",
    "monte_carlo_returns": "returns",
    "sequence_credit_assignment": "assign_sequence_credit",
    "td_returns": "td_target",
}

__all__ = [
    "EligibilityTraces",
    "assign_sequence_credit",
    "gae",
    "propagate",
    "returns",
    "td_target",
] + list(_ALIAS_EXPORTS)
