from __future__ import annotations

"""Executor instance binding helpers.

Keeps ``runtime.executor`` focused on sovereign execution entrypoints while the
mechanical state-to-attribute wiring lives on a single canonical path.
"""

from typing import Any


CANON_RUNTIME_EXECUTOR_BINDINGS = True


def apply_executor_state(*, executor: Any, state: Any) -> None:
    """Bind canonical assembled state to a RuntimeExecutor instance."""
    executor._ports = state.ports
    executor._guard = state.ports.guard
    executor._handlers = state.ports.handlers
    executor._events = state.ports.event_log
    executor._policy_registry = state.ports.policy_registry
    executor._reward = state.ports.reward_engine
    executor._learning = state.ports.learning_system
    executor._decision_core = state.ports.decision_core
    executor._runtime_infra = state.infra
    executor._outbox = state.infra.effect_outbox
    executor._archive = state.archive
    executor._constitution = state.constitution
    executor._economic_layer = state.economic_layer
    executor._snapshot_store = state.snapshot_store
    executor._max_meta_depth = state.max_meta_depth
    executor._cap_token = state.cap_token
    executor._effects = state.effects
    executor._reliability = getattr(state, "reliability", None)


__all__ = ["CANON_RUNTIME_EXECUTOR_BINDINGS", "apply_executor_state"]
