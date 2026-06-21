from __future__ import annotations

"""Runtime registration manifest.

The manifest is intentionally thin: action ownership remains in
``runtime.boot.actions_registry`` and stable constants remain in ``runtime.actions``.
This module wires handler registration without owning catalog rows.
"""

from collections.abc import Callable
from typing import Any

from runtime.actions import ACTION_AI_CEO_PLAN_V1
from runtime.boot.actions_registry import all_actions

CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_REGISTRATION_MANIFEST = True


def register_runtime_actions(*, handlers: Any, handler_factory: Callable[[str], Any] | None = None) -> tuple[str, ...]:
    """Register known runtime actions through the canonical action registry.

    ``handler_factory`` is required to produce concrete handlers; without it the
    manifest remains read-only and returns the canonical action list. This keeps
    the module from becoming a second catalog or hidden execution brain.
    """

    actions = tuple(sorted(all_actions() | {ACTION_AI_CEO_PLAN_V1}))
    if handler_factory is None:
        return actions
    for action in actions:
        handlers.register(action, handler_factory(action))
    return actions


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "CANON_RUNTIME_REGISTRATION_MANIFEST",
    "register_runtime_actions",
]
