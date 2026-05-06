from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class EconomicsSpendCapPolicyDefaults:
    zero_amount: float = 0.0
    soft_cap_ratio: float = 0.90


DEFAULT_ECONOMICS_SPEND_CAP_POLICY_DEFAULTS = EconomicsSpendCapPolicyDefaults()
