from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class HTTPSettings:
    host: str = "127.0.0.1"
    port: int = 8000
    enable_auth: bool = False
    auth_token: str = ""
    requests_per_minute: int = 60


__all__ = ["HTTPSettings"]
