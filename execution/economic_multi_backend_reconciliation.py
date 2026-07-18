from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from execution.economic_multi_backend_reconciliation_support import build_reconciliation_fields
CANON_ECONOMIC_MULTI_BACKEND_RECONCILIATION = True

@dataclass(frozen=True, slots=True)
class EconomicMultiBackendReconciliation:
    bundle_count: int
    node_count: int
    consistent: bool
    missing_feedback_event_ids: tuple[str, ...] = ()
    missing_roi_event_ids: tuple[str, ...] = ()
    missing_snapshot_ids: tuple[str, ...] = ()
    missing_trace_ids: tuple[str, ...] = ()
    missing_metrics_snapshot_ids: tuple[str, ...] = ()
    inconsistent_node_ids: tuple[str, ...] = ()
    quorum_size: int = 1
    quorum_achieved: bool = True
    segment_quorum: dict[str, Any] = field(default_factory=dict)
    scope_mismatch_node_ids: tuple[str, ...] = ()
    profile_mismatch_node_ids: tuple[str, ...] = ()
    corrupted_node_ids: tuple[str, ...] = ()
    stale_node_ids: tuple[str, ...] = ()
    authoritative_backend: str | None = None
    quorum_failure_segments: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {'bundle_count': int(self.bundle_count), 'node_count': int(self.node_count), 'consistent': bool(self.consistent), 'missing_feedback_event_ids': list(self.missing_feedback_event_ids), 'missing_roi_event_ids': list(self.missing_roi_event_ids), 'missing_snapshot_ids': list(self.missing_snapshot_ids), 'missing_trace_ids': list(self.missing_trace_ids), 'missing_metrics_snapshot_ids': list(self.missing_metrics_snapshot_ids), 'inconsistent_node_ids': list(self.inconsistent_node_ids), 'quorum_size': int(self.quorum_size), 'quorum_achieved': bool(self.quorum_achieved), 'segment_quorum': dict(self.segment_quorum), 'scope_mismatch_node_ids': list(self.scope_mismatch_node_ids), 'profile_mismatch_node_ids': list(self.profile_mismatch_node_ids), 'corrupted_node_ids': list(self.corrupted_node_ids), 'stale_node_ids': list(self.stale_node_ids), 'authoritative_backend': self.authoritative_backend, 'quorum_failure_segments': list(self.quorum_failure_segments), 'metadata': dict(self.metadata)}

class EconomicMultiBackendReconciliationBuilder:
    """Read-only integrity checker for canonical economic stores."""

    def build(self, *, feedback_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...], roi_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...], snapshot_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...], trace_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...], metrics_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...], bundle_payloads: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]=(), node_payloads: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]=(), quorum_size: int | None=None, segment_quorum_policy: Mapping[str, str] | None=None, backend_role_policy: Mapping[str, str] | None=None) -> EconomicMultiBackendReconciliation:
        fields = build_reconciliation_fields(feedback_rows=feedback_rows, roi_rows=roi_rows, snapshot_rows=snapshot_rows, trace_rows=trace_rows, metrics_rows=metrics_rows, bundle_payloads=bundle_payloads, node_payloads=node_payloads, quorum_size=quorum_size, segment_quorum_policy=segment_quorum_policy, backend_role_policy=backend_role_policy)
        return EconomicMultiBackendReconciliation(**fields)
__all__ = ['CANON_ECONOMIC_MULTI_BACKEND_RECONCILIATION', 'EconomicMultiBackendReconciliation', 'EconomicMultiBackendReconciliationBuilder']
