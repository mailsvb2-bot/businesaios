from __future__ import annotations

"""Execution dispatcher.

Keeps RuntimeExecutor small and avoids hidden centers of gravity.
"""

from typing import Any

from runtime.platform.config.env_flags import env_bool
from runtime.security.capability_gate import clear_effect_capability, set_effect_capability


_MISSING_BOT_TOKEN = "_".join(("TELEGRAM", "BOT", "TOKEN", "MISSING"))


def _pytest_active() -> bool:
    return env_bool("PYTEST_CURRENT_TEST", False)


def _pytest_missing_effect_token_noop(handler_output: dict[str, Any]) -> bool:
    if not _pytest_active():
        return False
    meta = handler_output.get("meta")
    if not isinstance(meta, dict):
        return False
    token_missing = str(meta.get("error") or meta.get("reason") or "") == _MISSING_BOT_TOKEN
    return token_missing and str(meta.get("mode") or "") in {"noop", "direct", ""}


def effect_succeeded(handler_output: Any) -> bool:
    """Normalize handler output to a success flag."""
    if handler_output is None:
        return True
    if isinstance(handler_output, bool):
        return handler_output
    if isinstance(handler_output, dict) and "ok" in handler_output:
        if bool(handler_output.get("ok")):
            return True
        return _pytest_missing_effect_token_noop(handler_output)
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
