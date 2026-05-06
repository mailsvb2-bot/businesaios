from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class CausalGuardrailsPolicy:
    min_n_days: int = 14
    negative_effect_threshold: float = 0.0
    insufficient_data_status: str = "insufficient_data"
    no_estimate_status: str = "no_estimate"
    warn_status: str = "warn"
    block_status: str = "block"
    ok_status: str = "ok"
    cautious_mode: str = "cautious"
    safe_mode: str = "safe"
    low_band: str = "low"


DEFAULT_CAUSAL_GUARDRAILS_POLICY = CausalGuardrailsPolicy()
