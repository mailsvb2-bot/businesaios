from __future__ import annotations

"""Compatibility shell for the canonical ``crm`` package root."""

import importlib
from typing import Any

CANONICAL_OWNER_CRM_PUBLIC_API = "crm"


def __getattr__(name: str) -> Any:
    module = importlib.import_module(CANONICAL_OWNER_CRM_PUBLIC_API)
    return getattr(module, name)


def __dir__() -> list[str]:
    module = importlib.import_module(CANONICAL_OWNER_CRM_PUBLIC_API)
    return sorted(set(dir(module)))


__all__ = []
