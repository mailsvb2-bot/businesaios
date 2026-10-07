from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MediaDeliveryMetricsSnapshot:
    tenant_id: str
    window_days: int
    generated_at_ms: int
    total: int
    delivered: int
    accepted: int
    failed: int
    by_channel: dict[str, int]
    by_kind: dict[str, int]


class MediaDeliveryMetricsProjection:
    """Read-only projection over canonical durable audio delivery events."""

    def __init__(self, event_store: Any) -> None:
        if event_store is None or not hasattr(event_store, "iter_events"):
            raise ValueError("event_store must provide iter_events(...)")
        self._events = event_store

    def build(
        self,
        *,
        tenant_id: str,
        window_days: int = 30,
        now_ms: int | None = None,
    ) -> MediaDeliveryMetricsSnapshot:
        tenant = str(tenant_id or "").strip()
        if not tenant:
            raise ValueError("tenant_id is required")
        days = int(window_days)
        if not 1 <= days <= 3650:
            raise ValueError("window_days must be between 1 and 3650")
        end_ms = int(now_ms) if now_ms is not None else int(time.time() * 1000)
        start_ms = max(0, end_ms - days * 24 * 3600 * 1000)

        total = delivered = accepted = failed = 0
        by_channel: dict[str, int] = {}
        by_kind: dict[str, int] = {}

        for event in self._events.iter_events(
            tenant_id=tenant,
            start_ms=start_ms,
            end_ms=end_ms,
            event_type="audio_sent",
        ):
            if str(event.get("event_type") or "") != "audio_sent":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            meta = payload.get("meta")
            meta = dict(meta) if isinstance(meta, dict) else {}
            channel = str(
                payload.get("channel")
                or meta.get("channel")
                or "telegram"
            ).strip().casefold() or "unknown"
            kind = str(payload.get("kind") or "voice").strip().casefold() or "unknown"

            total += 1
            by_channel[channel] = by_channel.get(channel, 0) + 1
            by_kind[kind] = by_kind.get(kind, 0) + 1

            ok = payload.get("ok") is True
            phase = str(meta.get("delivery_phase") or "").strip().casefold()
            finalized = meta.get("delivery_finalized") is True or phase == "finalized"
            if not ok:
                failed += 1
            elif finalized:
                delivered += 1
            else:
                accepted += 1

        return MediaDeliveryMetricsSnapshot(
            tenant_id=tenant,
            window_days=days,
            generated_at_ms=end_ms,
            total=total,
            delivered=delivered,
            accepted=accepted,
            failed=failed,
            by_channel=dict(sorted(by_channel.items())),
            by_kind=dict(sorted(by_kind.items())),
        )


__all__ = [
    "MediaDeliveryMetricsProjection",
    "MediaDeliveryMetricsSnapshot",
]
