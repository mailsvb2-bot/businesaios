from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid5

from contracts.event_store import append_event_strict, canonical_business_event_contract
from interfaces.ads.base import AdsPlatform, MetricPoint
from interfaces.ads.read_service import AdsReadService

CANON_ADS_METRICS_INGRESS = True
_EVENT_TYPE = "ads_metrics_imported"
_EVENT_NAMESPACE = UUID("9247744c-e4ff-4b16-8f23-337ee0eb4901")


def _required(name: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _day_ms(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp() * 1000)


@dataclass(frozen=True)
class AdsMetricsImportResult:
    imported: int
    replayed: int
    event_ids: tuple[str, ...]


@dataclass(frozen=True)
class AdsMetricsIngress:
    read_service: AdsReadService
    event_store: Any

    @staticmethod
    def _event_id(
        *,
        tenant_id: str,
        business_id: str,
        point: MetricPoint,
    ) -> str:
        ref = point.ref
        identity = ":".join(
            (
                tenant_id,
                business_id,
                ref.platform.value,
                ref.account_id,
                ref.object_type,
                ref.object_id,
                point.day.isoformat(),
            )
        )
        return str(uuid5(_EVENT_NAMESPACE, identity))

    def _existing(self, *, tenant_id: str, event_id: str, timestamp_ms: int) -> dict[str, Any] | None:
        end_ms = timestamp_ms + 86_400_000
        for event in self.event_store.iter_events(
            tenant_id=tenant_id,
            start_ms=timestamp_ms,
            end_ms=end_ms,
            event_type=_EVENT_TYPE,
        ):
            if str(event.get("event_id") or "") == event_id:
                return dict(event)
        return None

    @staticmethod
    def _event(
        *,
        tenant_id: str,
        business_id: str,
        point: MetricPoint,
        event_id: str,
    ) -> dict[str, Any]:
        ref = point.ref
        timestamp_ms = _day_ms(point.day)
        metrics = {
            "impressions": int(point.impressions),
            "clicks": int(point.clicks),
            "spend": float(point.spend),
            "conversions": None if point.conversions is None else int(point.conversions),
            "revenue": None if point.revenue is None else float(point.revenue),
            "cpa": None if point.cpa is None else float(point.cpa),
            "cpc": None if point.cpc is None else float(point.cpc),
            "ctr": None if point.ctr is None else float(point.ctr),
            "currency": None if point.currency is None else str(point.currency).strip().upper() or None,
        }
        return {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "user_id": None,
            "source": "runtime.ads.metrics_ingress",
            "event_type": _EVENT_TYPE,
            "timestamp_ms": timestamp_ms,
            "decision_id": None,
            "correlation_id": None,
            "payload": {
                "schema_version": 1,
                "business_id": business_id,
                "occurred_at_ms": timestamp_ms,
                "recorded_at_ms": timestamp_ms,
                "ref": {
                    "platform": ref.platform.value,
                    "account_id": ref.account_id,
                    "object_type": ref.object_type,
                    "object_id": ref.object_id,
                },
                "metrics": metrics,
            },
        }

    async def import_metrics(
        self,
        *,
        tenant_id: str,
        business_id: str,
        platform: AdsPlatform,
        account_id: str,
        level: str,
        object_ids: tuple[str, ...] | None,
        date_from: date,
        date_to: date,
    ) -> AdsMetricsImportResult:
        tenant = _required("tenant_id", tenant_id)
        business = _required("business_id", business_id)
        account = _required("account_id", account_id)
        normalized_level = _required("level", level)
        if date_to < date_from:
            raise ValueError("date_to must be >= date_from")
        points = tuple(
            await self.read_service.fetch_metrics(
                tenant_id=tenant,
                platform=platform,
                account_id=account,
                level=normalized_level,
                object_ids=object_ids,
                date_from=date_from,
                date_to=date_to,
            )
        )
        imported = 0
        replayed = 0
        event_ids: list[str] = []
        for point in points:
            if point.ref.platform is not platform:
                raise ValueError("ads metric platform mismatch")
            if str(point.ref.account_id) != account:
                raise ValueError("ads metric account mismatch")
            if point.day < date_from or point.day > date_to:
                raise ValueError("ads metric day outside requested range")
            event_id = self._event_id(
                tenant_id=tenant,
                business_id=business,
                point=point,
            )
            event = self._event(
                tenant_id=tenant,
                business_id=business,
                point=point,
                event_id=event_id,
            )
            existing = self._existing(
                tenant_id=tenant,
                event_id=event_id,
                timestamp_ms=int(event["timestamp_ms"]),
            )
            if existing is not None:
                if canonical_business_event_contract(existing) != canonical_business_event_contract(event):
                    raise RuntimeError("ADS_METRICS_IMPORT_CONFLICT")
                replayed += 1
                event_ids.append(event_id)
                continue
            append_event_strict(self.event_store, tenant_id=tenant, event=event)
            stored = self._existing(
                tenant_id=tenant,
                event_id=event_id,
                timestamp_ms=int(event["timestamp_ms"]),
            )
            if stored is None:
                raise RuntimeError("ADS_METRICS_IMPORT_NOT_DURABLE")
            if canonical_business_event_contract(stored) != canonical_business_event_contract(event):
                raise RuntimeError("ADS_METRICS_IMPORT_CONFLICT")
            imported += 1
            event_ids.append(event_id)
        return AdsMetricsImportResult(
            imported=imported,
            replayed=replayed,
            event_ids=tuple(event_ids),
        )


__all__ = [
    "AdsMetricsImportResult",
    "AdsMetricsIngress",
    "CANON_ADS_METRICS_INGRESS",
]
