from __future__ import annotations

from core.world_model.types import CustomerState


class CustomerStateBuilder:
    def build(self, payload: dict | None) -> CustomerState:
        data = dict(payload or {})
        return CustomerState(
            customer_id=str(data.get("customer_id") or "unknown"),
            stage=str(data.get("stage") or "unknown"),
            segment=str(data.get("segment") or "unknown"),
            sessions_30d=int(data.get("sessions_30d") or 0),
            purchases_30d=int(data.get("purchases_30d") or 0),
            last_seen_at_ms=data.get("last_seen_at_ms"),
            traits=dict(data.get("traits") or {}),
        )
