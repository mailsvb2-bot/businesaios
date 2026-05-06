from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorityScope:
    OPS: str = "ops"
    RISK: str = "risk"
    PRODUCT: str = "product"
    FINANCE: str = "finance"
    SECURITY: str = "security"
    PLATFORM: str = "platform"
    EXECUTIVE: str = "executive"
