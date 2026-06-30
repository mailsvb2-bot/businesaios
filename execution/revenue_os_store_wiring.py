"""Compatibility surface for legacy execution imports.

Canonical ownership for revenue advisory persistence wiring lives in
runtime.monetization.revenue_advisory_store. This module stays as a thin import
boundary so execution callers do not grow a parallel persistence owner.
"""

from __future__ import annotations

from runtime.monetization.revenue_advisory_store import CANON_RUNTIME_MONETIZATION_REVENUE_ADVISORY_STORE
from runtime.monetization.revenue_advisory_store import FileRevenueExperimentRegistry
from runtime.monetization.revenue_advisory_store import JsonlAppendOnlyStore
from runtime.monetization.revenue_advisory_store import RegisteredRevenueExperiment
from runtime.monetization.revenue_advisory_store import RevenueAdvisoryStoreWiring
from runtime.monetization.revenue_advisory_store import RevenueAppendOnlyStore
from runtime.monetization.revenue_advisory_store import build_revenue_advisory_store_wiring

CANON_EXECUTION_REVENUE_OS_STORE_WIRING = True
RevenueOSStoreWiring = RevenueAdvisoryStoreWiring
build_revenue_os_store_wiring = build_revenue_advisory_store_wiring
__all__ = [
    'CANON_EXECUTION_REVENUE_OS_STORE_WIRING',
    'CANON_RUNTIME_MONETIZATION_REVENUE_ADVISORY_STORE',
    'FileRevenueExperimentRegistry',
    'JsonlAppendOnlyStore',
    'RegisteredRevenueExperiment',
    'RevenueAppendOnlyStore',
    'RevenueOSStoreWiring',
    'build_revenue_os_store_wiring',
]

