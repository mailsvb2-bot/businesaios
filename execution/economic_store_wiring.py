from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path
import platform

from execution.economic_memory_store import JsonlEconomicMemoryStore
from execution.economic_bundle_quarantine_store import JsonlEconomicBundleQuarantineStore
from execution.replay_safe_roi_history import JsonlROIHistoryStore
from execution.economic_scope_profile import EconomicScopeProfileResolver
from observability.economic_policy_snapshot_store import JsonlEconomicPolicySnapshotStore
from observability.economic_trace_store import JsonlEconomicTraceStore
from observability.economic_metrics_store import JsonlEconomicMetricsStore
from compliance.economic_forensics_store import JsonlEconomicForensicsStore

CANON_ECONOMIC_STORE_WIRING = True


@dataclass(frozen=True, slots=True)
class EconomicStoreBundle:
    trace_store: JsonlEconomicTraceStore
    policy_snapshot_store: JsonlEconomicPolicySnapshotStore
    memory_store: JsonlEconomicMemoryStore
    roi_history_store: JsonlROIHistoryStore
    metrics_store: JsonlEconomicMetricsStore
    quarantine_store: JsonlEconomicBundleQuarantineStore
    forensics_store: JsonlEconomicForensicsStore
    root_dir: str
    bundles_dir: str
    bundle_catalog_path: str
    retention_policy: dict[str, Any]
    node_id: str


class EconomicStoreWiring:
    """
    Persistent wiring helper for economic stores.

    Important:
    - Does not compute policy.
    - Does not introduce a second brain.
    - Only creates canonical persistent backends for existing economic stores.
    """

    def __init__(self, *, root_dir: str | Path) -> None:
        self._root = Path(root_dir)

    def build(self) -> EconomicStoreBundle:
        root = self._root / 'economic'
        root.mkdir(parents=True, exist_ok=True)
        bundles_dir = root / 'bundles'
        bundles_dir.mkdir(parents=True, exist_ok=True)
        catalog_path = root / 'bundle_catalog.json'
        base_retention = {
            'max_feedback_rows': 250,
            'max_roi_rows': 250,
            'max_snapshot_rows': 250,
            'max_trace_rows': 250,
            'max_metrics_rows': 250,
            'max_age_days': 30,
            'max_snapshot_age_days': 60,
            'preserve_audit_summary': True,
            'metadata': {'owner': 'execution.economic_store_wiring'},
        }
        resolved = EconomicScopeProfileResolver(base_retention_policy=base_retention).resolve(
            action={'tenant_tier': 'standard', 'business_tier': 'standard'},
            execution_receipt={},
            economic_policy={},
        )
        quarantine_store = JsonlEconomicBundleQuarantineStore(root / 'bundle_quarantine.jsonl')
        forensics_store = JsonlEconomicForensicsStore(root / 'compliance_forensics.jsonl')
        return EconomicStoreBundle(
            trace_store=JsonlEconomicTraceStore(root / 'trace.jsonl'),
            policy_snapshot_store=JsonlEconomicPolicySnapshotStore(root / 'policy_snapshots.jsonl'),
            memory_store=JsonlEconomicMemoryStore(root / 'memory_feedback.jsonl'),
            roi_history_store=JsonlROIHistoryStore(root / 'roi_history.jsonl'),
            metrics_store=JsonlEconomicMetricsStore(root / 'metrics_snapshots.jsonl'),
            quarantine_store=quarantine_store,
            forensics_store=forensics_store,
            root_dir=str(root),
            bundles_dir=str(bundles_dir),
            bundle_catalog_path=str(catalog_path),
            retention_policy=resolved.retention_policy,
            node_id=platform.node() or 'local-primary',
        )


__all__ = [
    'CANON_ECONOMIC_STORE_WIRING',
    'EconomicStoreBundle',
    'EconomicStoreWiring',
]
