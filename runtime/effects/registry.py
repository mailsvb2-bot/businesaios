"""Removed legacy effect-action registry compatibility surface.

Executable action names and handlers are owned exclusively by
``runtime.boot.actions_registry`` and ``runtime.handlers.ActionHandlerRegistry``.
Keeping a second mapping here previously allowed actions to appear supported
without being dispatchable by RuntimeExecutor.
"""

from __future__ import annotations

CANON_LEGACY_EFFECT_REGISTRY_REMOVED = True


def build_registry(_effects_impl):
    raise RuntimeError(
        "LEGACY_EFFECT_ACTION_REGISTRY_REMOVED:use_runtime_handler_registry"
    )


__all__ = [
    "CANON_LEGACY_EFFECT_REGISTRY_REMOVED",
    "build_registry",
]
