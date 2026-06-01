from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class AppSettings:
    environment: str = "dev"


__all__ = ["AppSettings"]
