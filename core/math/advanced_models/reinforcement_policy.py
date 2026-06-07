from __future__ import annotations

import random
from collections.abc import Hashable, Sequence

State = Hashable
Action = Hashable
QTable = dict[State, dict[Action, float]]

def q_learning_update(
    q_table: QTable,
    *,
    state: State,
    action: Action,
    reward: float,
    next_state: State,
    next_actions: Sequence[Action],
    alpha: float = 0.1,
    gamma: float = 0.95,
) -> float:
    if not next_actions:
        raise ValueError("next_actions must be non-empty")
    q_table.setdefault(state, {})
    q_table[state].setdefault(action, 0.0)
    q_table.setdefault(next_state, {})
    for next_action in next_actions:
        q_table[next_state].setdefault(next_action, 0.0)
    old_q = q_table[state][action]
    max_next_q = max(q_table[next_state][a] for a in next_actions)
    updated = old_q + alpha * (reward + gamma * max_next_q - old_q)
    q_table[state][action] = updated
    return updated

def select_epsilon_greedy_action(
    q_table: QTable,
    *,
    state: State,
    actions: Sequence[Action],
    epsilon: float,
    random_seed: int | None = None,
) -> Action:
    if not actions:
        raise ValueError("actions must be non-empty")
    rng = random.Random(random_seed)
    q_table.setdefault(state, {})
    for action in actions:
        q_table[state].setdefault(action, 0.0)
    if rng.random() < epsilon:
        return rng.choice(list(actions))
    return max(actions, key=lambda a: q_table[state][a])
