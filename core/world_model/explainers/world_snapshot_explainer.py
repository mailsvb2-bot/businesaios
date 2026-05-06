from __future__ import annotations

from core.world_model.types import WorldSnapshot


class WorldSnapshotExplainer:
    def explain(self, *, snapshot: WorldSnapshot) -> dict:
        return {
            "summary": (
                f"snapshot={snapshot.snapshot_id}; tenant={snapshot.tenant_id}; "
                f"correlation={snapshot.correlation_id}; business={snapshot.business_id}; confidence={snapshot.confidence}"
            ),
            "confidence_reasons": list(snapshot.confidence_report.reasons) if snapshot.confidence_report else [],
            "freshness": {k: v.value for k, v in (snapshot.freshness.per_reader.items() if snapshot.freshness else [])},
        }


def explain_world_snapshot(snapshot: WorldSnapshot) -> str:
    return (
        f"tenant={snapshot.tenant_id}; "
        f"correlation={snapshot.correlation_id}; "
        f"confidence={snapshot.confidence}"
    )
