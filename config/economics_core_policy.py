from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class EconomicsCorePolicy:
    target_cac_rub: int = 600
    target_payback_days: int = 30
    min_ltv_cac_ratio: float = 2.0


DEFAULT_ECONOMICS_CORE_POLICY = EconomicsCorePolicy()
