from __future__ import annotations

from core.finance.strategic.adapters.economics_snapshot_adapter import EconomicsSnapshotToFinancialInputAdapter as EconomicsSnapshotFinancialInputAdapter

# Compatibility import only. This file must never add extra logic or a second
# implementation path; it exists only to preserve stable imports while routing
# every caller into the canonical adapter.
# pass

__all__ = ['EconomicsSnapshotFinancialInputAdapter']
