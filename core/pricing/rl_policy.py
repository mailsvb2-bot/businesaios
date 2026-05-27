from __future__ import annotations

"""Minimal RL policy interface (compat).

The production-safe RL pricing picker in this repo is implemented in
:mod:`core.pricing.rl_picker` and the rollout/guard primitives in
:mod:`core.pricing.rl_rollout`.

This module provides a tiny, dependency-free policy object for callers/tests
that expect a 'choose_action' shape.
"""

import random
from typing import Any, Sequence


class RLPricePolicy:
    def __init__(self, actions: Sequence[Any]):
        self._actions = list(actions)

    def choose_action(self, state: Any) -> Any:
        # Stateless baseline policy: random among provided actions.
        # Real policies are implemented via event-sourced bandit in rl_picker.
        if not self._actions:
            raise ValueError("EMPTY_ACTIONS")
        return random.choice(self._actions)
