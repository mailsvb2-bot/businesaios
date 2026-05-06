from __future__ import annotations

from core.world_model.contracts import WORLD_SNAPSHOT_SCHEMA_VERSION
from core.world_model.enums import SnapshotStatus
from core.world_model.types import (
    BusinessState,
    CompletenessReport,
    ConfidenceReport,
    FreshnessReport,
    WorldSnapshot,
    WorldSnapshotRequest,
)


class WorldSnapshotBuilder:
    def build(
        self,
        request: WorldSnapshotRequest,
        *,
        business_id: str = "",
        snapshot_id: str = "",
        built_at_ms: int = 0,
        business_state: BusinessState | None = None,
        freshness: FreshnessReport | None = None,
        completeness: CompletenessReport | None = None,
        confidence_report: ConfidenceReport | None = None,
        explain: dict | None = None,
        metadata: dict | None = None,
    ) -> WorldSnapshot:
        confidence_value = float(confidence_report.score) if confidence_report is not None else 0.0
        return WorldSnapshot(
            tenant_id=str(request.tenant_id),
            correlation_id=str(request.correlation_id),
            confidence=confidence_value,
            business_id=str(business_id),
            snapshot_id=str(snapshot_id),
            built_at_ms=int(built_at_ms),
            schema_version=WORLD_SNAPSHOT_SCHEMA_VERSION,
            status=SnapshotStatus.ACCEPTED,
            business_state=business_state,
            freshness=freshness,
            completeness=completeness,
            confidence_report=confidence_report,
            explain=dict(explain or {}),
            metadata=dict(metadata or {}),
        )


def build_empty_world_snapshot(request: WorldSnapshotRequest) -> WorldSnapshot:
    return WorldSnapshotBuilder().build(request)
