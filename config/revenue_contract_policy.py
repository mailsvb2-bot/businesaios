from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class RevenueContractPolicy:
    zero_revenue: float = 0.0
    empty_title: str = ""
    empty_text: str = ""


DEFAULT_REVENUE_CONTRACT_POLICY = RevenueContractPolicy()
