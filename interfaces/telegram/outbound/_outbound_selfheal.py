from __future__ import annotations

"""Compatibility re-export for canonical Telegram outbound self-heal primitives."""

from interfaces.telegram.outbound.outbound_self_heal import (
    SelfHealConfig,
    SelfHealController,
    maybe_self_heal,
    purge_backlog,
)

__all__ = [
    "SelfHealConfig",
    "SelfHealController",
    "maybe_self_heal",
    "purge_backlog",
]
