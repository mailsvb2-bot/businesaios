from __future__ import annotations

from demand_product.magic_moment_publisher import MagicMomentPublisher as DemandMagicMomentPublisher


class MagicMomentPublisher:
    def __init__(self, *, publisher: DemandMagicMomentPublisher | None = None) -> None:
        self._publisher = publisher or DemandMagicMomentPublisher()

    def publish(self, payload: dict) -> dict:
        normalized = dict(payload or {})
        event_payload = dict(normalized.get("payload") or normalized)
        published = self._publisher.publish(
            code=str(normalized.get("kind") or event_payload.get("code") or "magic_moment"),
            business_id=str(event_payload.get("business_id") or ""),
        )
        return {"kind": "magic_moment_event", "payload": published}
