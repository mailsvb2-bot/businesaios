from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class SpendLedgerPolicy:
    zero_value: float = 0.0
    uncertainty_marker: float = 1.0
    block_minor_units: int = 10**12
    major_to_minor_multiplier: int = 100


DEFAULT_SPEND_LEDGER_POLICY = SpendLedgerPolicy()
