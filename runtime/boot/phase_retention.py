from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


import os
from contextlib import ExitStack
from typing import Any

from bootstrap.failure_policy import resolve_optional_boot_component


def build_retention_adapter(
    *,
    FeatureFlags: Any,
    event_store: Any,
    tenant_id: str,
    telegram_outbound_queue: Any,
    base: str,
    stack: ExitStack,
):
    from core.retention.decision_adapter import RetentionDecisionAdapter
    from core.offers.engine import OfferEngine

    if not FeatureFlags.RETENTION:
        return None

    retention_prices = _load_retention_prices()
    retention_outbound_metrics = _build_retention_outbound_metrics_reader(
        telegram_outbound_queue=telegram_outbound_queue,
    )
    offer_engine = OfferEngine.default()
    cooldown_store = _open_cooldown_store(base=base, stack=stack)

    return RetentionDecisionAdapter(
        event_store=event_store,
        tenant_id=tenant_id,
        prices=retention_prices,
        outbound_metrics_reader=retention_outbound_metrics,
        offer_engine=offer_engine,
        offer_cooldown_store=cooldown_store,
    )



def _load_retention_prices() -> dict[str, int] | None:
    def _builder() -> dict[str, int] | None:
        from core.retention.config.pricing_ladder import retention_boot_prices
        return retention_boot_prices()

    return resolve_optional_boot_component(
        component="retention_prices",
        builder=_builder,
        fallback=None,
    )



def _build_retention_outbound_metrics_reader(*, telegram_outbound_queue: Any):
    if telegram_outbound_queue is None:
        return None

    def retention_outbound_metrics():
        snap = (
            telegram_outbound_queue.metrics_snapshot()
            if hasattr(telegram_outbound_queue, "metrics_snapshot")
            else {}
        )
        be = (snap.get("by_priority") or {}).get("best_effort") or {}
        p95 = (be.get("wait_ms") or {}).get("p95") or 0.0
        return {"qsize": snap.get("qsize", 0), "p90_wait_ms": float(p95)}

    return retention_outbound_metrics



def _open_cooldown_store(*, base: str, stack: ExitStack):
    def _builder():
        from observability.platform.snapshot_store.offer_cooldowns_sqlite import OfferCooldownStoreSqlite
        db_path = os.path.join(str(base), "offer_cooldowns.db")
        cooldown_store = OfferCooldownStoreSqlite(path=str(db_path)).open()
        stack.callback(cooldown_store.close)
        return cooldown_store

    return resolve_optional_boot_component(
        component="retention_cooldown_store",
        builder=_builder,
        fallback=None,
    )
