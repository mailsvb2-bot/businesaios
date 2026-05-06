from __future__ import annotations

"""Execution dispatcher.

Keeps RuntimeExecutor small and avoids hidden centers of gravity.
"""

from typing import Any

from runtime.security.capability_gate import set_effect_capability, clear_effect_capability


def effect_succeeded(handler_output: Any) -> bool:
    """Normalize handler output to a success flag."""
    if handler_output is None:
        return True
    if isinstance(handler_output, bool):
        return handler_output
    if isinstance(handler_output, dict) and "ok" in handler_output:
        return bool(handler_output.get("ok"))
    return bool(handler_output)


def dispatch_action(*, handlers, effects, cap_token: str, action: str, payload: dict) -> Any:
    """Dispatch an action to its handler under an issued capability."""

    handler = handlers.get(action)
    if handler is None:
        raise RuntimeError(f"UNKNOWN_ACTION:{action}")

    tok = set_effect_capability(cap_token)
    try:
        return handler(payload, effects)
    finally:
        clear_effect_capability(tok)
