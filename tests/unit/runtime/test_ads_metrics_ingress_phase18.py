from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from core.growth.spend_ledger_event_store import EventStoreSpendLedger
from interfaces.ads.base import AdsObjectRef, AdsPlatform, MetricPoint
from runtime.ads.metrics_ingress import AdsMetricsIngress
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _ReadService:
    def __init__(self, point: MetricPoint) -> None:
        self.point = point
        self.calls = []

    async def fetch_metrics(self, **kwargs):
        self.calls.append(dict(kwargs))
        return (self.point,)


def _point(*, spend: float = 12.5) -> MetricPoint:
    return MetricPoint(
        ref=AdsObjectRef(
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="account-1",
            object_type="campaign",
            object_id="campaign-1",
        ),
        day=date(2026, 10, 7),
        impressions=100,
        clicks=10,
        spend=spend,
        conversions=2,
        revenue=30.0,
        currency="RUB",
    )


@pytest.mark.asyncio
async def test_ads_metrics_ingress_is_business_scoped_and_replay_safe() -> None:
    events = MemoryEventStore()
    reader = _ReadService(_point())
    ingress = AdsMetricsIngress(read_service=reader, event_store=events)

    first = await ingress.import_metrics(
        tenant_id="tenant-a",
        business_id="business-a",
        platform=AdsPlatform.GOOGLE_ADS,
        account_id="account-1",
        level="campaign",
        object_ids=("campaign-1",),
        date_from=date(2026, 10, 7),
        date_to=date(2026, 10, 7),
    )
    replay = await ingress.import_metrics(
        tenant_id="tenant-a",
        business_id="business-a",
        platform=AdsPlatform.GOOGLE_ADS,
        account_id="account-1",
        level="campaign",
        object_ids=("campaign-1",),
        date_from=date(2026, 10, 7),
        date_to=date(2026, 10, 7),
    )
    other_business = await ingress.import_metrics(
        tenant_id="tenant-a",
        business_id="business-b",
        platform=AdsPlatform.GOOGLE_ADS,
        account_id="account-1",
        level="campaign",
        object_ids=("campaign-1",),
        date_from=date(2026, 10, 7),
        date_to=date(2026, 10, 7),
    )

    assert (first.imported, first.replayed) == (1, 0)
    assert (replay.imported, replay.replayed) == (0, 1)
    assert (other_business.imported, other_business.replayed) == (1, 0)
    assert first.event_ids != other_business.event_ids

    stored = list(
        events.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
            event_type="ads_metrics_imported",
        )
    )
    assert len(stored) == 2
    assert {row["payload"]["business_id"] for row in stored} == {
        "business-a",
        "business-b",
    }
    assert {row["payload"]["ref"]["account_id"] for row in stored} == {"account-1"}

    start_ms = int(datetime(2026, 10, 7, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 10, 8, tzinfo=UTC).timestamp() * 1000)
    ledger = EventStoreSpendLedger(event_store=events)
    assert ledger.spend_minor_range(
        tenant_id="tenant-a",
        business_id="business-a",
        start_ms=start_ms,
        end_ms=end_ms,
    ) == 1250
    assert ledger.spend_minor_range(
        tenant_id="tenant-a",
        business_id="business-b",
        start_ms=start_ms,
        end_ms=end_ms,
    ) == 1250


@pytest.mark.asyncio
async def test_ads_metrics_ingress_rejects_conflicting_reimport() -> None:
    events = MemoryEventStore()
    reader = _ReadService(_point(spend=12.5))
    ingress = AdsMetricsIngress(read_service=reader, event_store=events)
    kwargs = dict(
        tenant_id="tenant-a",
        business_id="business-a",
        platform=AdsPlatform.GOOGLE_ADS,
        account_id="account-1",
        level="campaign",
        object_ids=("campaign-1",),
        date_from=date(2026, 10, 7),
        date_to=date(2026, 10, 7),
    )

    await ingress.import_metrics(**kwargs)
    reader.point = _point(spend=15.0)

    with pytest.raises(RuntimeError, match="ADS_METRICS_IMPORT_CONFLICT"):
        await ingress.import_metrics(**kwargs)


@pytest.mark.asyncio
async def test_ads_metrics_ingress_rejects_connector_scope_drift() -> None:
    events = MemoryEventStore()
    reader = _ReadService(
        MetricPoint(
            ref=AdsObjectRef(
                platform=AdsPlatform.GOOGLE_ADS,
                account_id="different-account",
                object_type="campaign",
                object_id="campaign-1",
            ),
            day=date(2026, 10, 7),
            impressions=1,
            clicks=0,
            spend=0.0,
        )
    )
    ingress = AdsMetricsIngress(read_service=reader, event_store=events)

    with pytest.raises(ValueError, match="ads metric account mismatch"):
        await ingress.import_metrics(
            tenant_id="tenant-a",
            business_id="business-a",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="account-1",
            level="campaign",
            object_ids=("campaign-1",),
            date_from=date(2026, 10, 7),
            date_to=date(2026, 10, 7),
        )
    assert list(events.iter_events(tenant_id="tenant-a", start_ms=0)) == []
