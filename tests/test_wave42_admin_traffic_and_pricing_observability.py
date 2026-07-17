from __future__ import annotations

from pathlib import Path

from config.yaml_loader_shared import load_yaml
from core.admin.read_models.traffic import (
    demo_summary,
    funnel2_report,
    users_today,
)
from runtime.admin_pricing import execute_offer_price_update
from runtime.admin_state_support import build_pricing_change_payload


class _Store:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        event_type: str | None = None,
    ):
        del tenant_id
        for event in self._events:
            if int(event.get("ts_ms", 0)) < int(start_ms):
                continue
            if (
                event_type is not None
                and str(event.get("event_type")) != str(event_type)
            ):
                continue
            yield dict(event)


def test_traffic_read_models_respect_explicit_now_ms() -> None:
    day_start = 1_699_920_000_000
    store = _Store(
        [
            {
                "ts_ms": day_start - 2 * 24 * 3600 * 1000,
                "user_id": "old",
                "event_type": "audio_sent",
                "payload": {"path": "home"},
            },
            {
                "ts_ms": day_start + 1000,
                "user_id": "u1",
                "event_type": "audio_sent",
                "payload": {"path": "work"},
            },
            {
                "ts_ms": day_start + 2000,
                "user_id": "u2",
                "event_type": "tariffs_viewed",
                "payload": {},
            },
        ]
    )
    explicit_now_ms = day_start + 10_000
    assert users_today(store, now_ms=explicit_now_ms) == 2
    assert demo_summary(store, days=1, now_ms=explicit_now_ms) == {
        "sent_work": 1,
        "sent_home": 0,
        "users": 1,
    }
    report = funnel2_report(store, days=1, now_ms=explicit_now_ms)
    assert report["start_ms"] == explicit_now_ms - 24 * 3600 * 1000
    assert report["counts"]["tariffs_viewed"] == 1


def test_execute_offer_price_update_reports_catalog_revision(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "tenant-demo-product-demo-dev.yaml"
    catalog_path.write_text(
        "catalog_id: tenant-demo:product-demo:dev\n"
        "pricing_version: v2.0\n"
        "offers:\n"
        "  - offer_id: offer-7\n"
        "    base_price_rub: 100\n"
        "    meta:\n"
        "      plan_id: 7\n",
        encoding="utf-8",
    )

    result = execute_offer_price_update(
        tenant_id="tenant-demo",
        product_id="product-demo",
        environment="dev",
        plan_id=7,
        new_price=150,
        pricing_version="v2.1",
        catalog_path=catalog_path,
    )

    assert result["offer_id"] == "offer-7"
    assert result["plan_id"] == 7
    assert result["old_price"] == 100
    assert result["new_price"] == 150
    assert result["pricing_version"] == "v2.1"
    assert result["catalog_path"] == str(catalog_path.resolve())
    assert (
        result["catalog_revision_before"]
        != result["catalog_revision_after"]
    )

    updated = load_yaml(
        catalog_path,
        allow_empty=False,
        cache=False,
    )
    assert updated["pricing_version"] == "v2.1"
    assert updated["offers"][0]["base_price_rub"] == 150


def test_build_pricing_change_payload_is_canonical() -> None:
    payload = build_pricing_change_payload(
        request_id="req-1",
        plan_id=11,
        new_price=777,
        pricing_version="v9",
        requested_by="admin-1",
        reason="manual review",
        plans_path="data/plans.json",
        override_path="data/override.txt",
        override_persisted=True,
    )
    assert payload == {
        "request_id": "req-1",
        "plan_id": 11,
        "new_price": 777,
        "pricing_version": "v9",
        "requested_by": "admin-1",
        "reason": "manual review",
        "plans_path": "data/plans.json",
        "override_path": "data/override.txt",
        "override_persisted": True,
    }
