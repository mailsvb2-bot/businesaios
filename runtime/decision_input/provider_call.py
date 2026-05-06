from __future__ import annotations

"""Canonical provider-call discipline for runtime decision input.

This module prevents false fallback behavior where an internal ``TypeError``
from a provider implementation could be mistaken for a signature mismatch and
silently retried on a narrower path. We inspect the callable contract up front
and only degrade when the signature truly does not accept the richer runtime
packet inputs.
"""

import importlib
from typing import Any, Callable

CANON_RUNTIME_DECISION_INPUT_PROVIDER_CALL = True

_FULL_KWARGS = (
    "world_state",
    "proposal",
    "generated_at_ms",
    "safe_mode",
)


def call_decision_input_provider(
    *,
    build_fn: Callable[..., Any],
    world_state: Any,
    proposal: dict[str, Any],
    generated_at_ms: int,
    safe_mode: bool,
) -> Any:
    accepts_keywords = importlib.import_module("core.utils.call_signature").accepts_keywords
    if accepts_keywords(build_fn, _FULL_KWARGS):
        return build_fn(
            world_state=world_state,
            proposal=dict(proposal),
            generated_at_ms=int(generated_at_ms),
            safe_mode=bool(safe_mode),
        )
    return build_fn(world_state=world_state)


__all__ = [
    "CANON_RUNTIME_DECISION_INPUT_PROVIDER_CALL",
    "call_decision_input_provider",
]
