"""Call-origin assertions.

Used to enforce architectural sovereignty at runtime without creating layer violations.

This module lives in *core* so that both core and runtime can depend on it.
"""

from __future__ import annotations

import inspect
from importlib import import_module

def _is_bootstrap_context_active() -> bool:
    try:
        module = import_module("runtime.boot.entrypoint_context")
    except Exception:
        return False
    checker = getattr(module, "is_bootstrap_entrypoint_active", None)
    if checker is None:
        return False
    try:
        return bool(checker())
    except Exception:
        return False


def assert_called_from_runtime_executor() -> None:
    """Hard-fail if current call stack is not originating from runtime/executor.py."""
    for frame in inspect.stack()[1:]:
        filename = frame.filename.replace("\\", "/")
        if filename.endswith("/runtime/executor.py") or "/runtime/executor.py" in filename:
            return
    raise RuntimeError("SIDE_EFFECT_OUTSIDE_RUNTIME_EXECUTOR")


def assert_called_from_bootstrap() -> None:
    """Allow-list for wiring-time calls.

    Policy registration and other *pure wiring* operations may only be called
    from the sovereign entrypoint or tests.
    """
    if _is_bootstrap_context_active():
        return
    for frame in inspect.stack()[1:]:
        filename = frame.filename.replace("\\", "/")
        if filename.endswith("/main.py") or "/main.py" in filename:
            return
        if "/tests/" in filename or filename.endswith("/conftest.py"):
            return
    raise RuntimeError("WIRING_CALL_OUTSIDE_ENTRYPOINT")
