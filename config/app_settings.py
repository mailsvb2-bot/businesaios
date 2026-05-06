from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class AppSettings:
    environment: str = "dev"


__all__ = ["AppSettings"]
