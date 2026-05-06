from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.analytics.analytics_materializer import AnalyticsMaterializer
from application.analytics.distributed_analytics_materializer_lock import PersistentAnalyticsMaterializerLock


@dataclass
class PersistentDistributedAnalyticsMaterializer:
    materializer: AnalyticsMaterializer
    lock: PersistentAnalyticsMaterializerLock

    def materialize_for_tenant(
        self,
        *,
        tenant_id: str,
        window_days: int = 30,
        export_path: str | None = None,
    ) -> dict[str, Any]:
        leadership = self.lock.acquire(tenant_id=str(tenant_id))
        try:
            if not self.lock.validate(leadership=leadership):
                raise RuntimeError("analytics materializer leadership validation failed")
            result = self.materializer.materialize_for_tenant(
                tenant_id=str(tenant_id),
                window_days=int(window_days),
                export_path=export_path,
            )
            result["leadership"] = {
                "tenant_id": leadership.tenant_id,
                "leader_id": leadership.leader_id,
                "resource": leadership.resource,
                "fencing_token": leadership.fencing_token.as_int(),
                "acquired_at": leadership.acquired_at.isoformat(),
                "expires_at": leadership.expires_at.isoformat(),
            }
            return result
        finally:
            self.lock.release(leadership=leadership)
