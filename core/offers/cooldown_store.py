from __future__ import annotations

from importlib import import_module
from typing import Any


def __getattr__(name: str) -> Any:
    if name == "OfferCooldownStoreSqlite":
        module = import_module("observability.platform.snapshot_store.offer_cooldowns_sqlite")
        return getattr(module, "OfferCooldownStoreSqlite")
    raise AttributeError(name)


__all__ = ["OfferCooldownStoreSqlite"]
