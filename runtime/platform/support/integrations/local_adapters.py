from __future__ import annotations

"""Concrete local platform-support integrations collected behind one public facade.

The actual adapter implementations are split by role so the facade stays small
and import-stable while local/offline integrations remain discoverable from one
canonical module path.
"""

from runtime.platform.support.integrations._local_adapters_io import SQLAdapter, TracingAdapter
from runtime.platform.support.integrations._local_adapters_state import (
    ExperimentTrackerAdapter,
    FeatureStoreAdapter,
    MessageBusAdapter,
    MetricsAdapter,
    ObjectStoreAdapter,
    SchedulerAdapter,
    SecretsManagerAdapter,
)

__all__ = [
    "ExperimentTrackerAdapter",
    "FeatureStoreAdapter",
    "MessageBusAdapter",
    "MetricsAdapter",
    "ObjectStoreAdapter",
    "SchedulerAdapter",
    "SecretsManagerAdapter",
    "SQLAdapter",
    "TracingAdapter",
]
