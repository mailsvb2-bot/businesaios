"""Telegram runner component factory.

Contract: decide_fn MUST be DecisionCore.decide (single decision source).
No alternate decision path or second brain; all loops receive the same injected decide_fn.
"""
from __future__ import annotations

from typing import Any

from core.tenancy.tenant import current_tenant_id
from interfaces.telegram.pipeline.poller import TelegramPoller, PollerConfig
from interfaces.telegram.pipeline.update_processor import TelegramUpdateProcessor
from interfaces.telegram.read_models.enricher import TelegramReadModelEnricher
from interfaces.telegram.runtime_loops.ml_loop import MLLearningLoop, MLLooopConfig
from interfaces.telegram.runtime_loops.offer_outcome import OfferOutcomeConfig, OfferOutcomeLoop
from interfaces.telegram.runtime_loops.payment_jobs import PaymentJobsConfig, PaymentJobsLoop
from interfaces.telegram.runtime_loops.reconcile import PaymentsReconcileLoop, ReconcileConfig
from interfaces.telegram.runner_helpers import env_hours, env_int, env_ms
from products.product_loader import load_product_from_env


def _bounded_int(name: str, default: int, lo: int, hi: int) -> int:
    return max(int(lo), min(int(hi), int(env_int(name, int(default)))))


def build_runner_components(*, decide_fn: Any, execute_fn: Any, event_store: Any, event_log: Any, payment_outbox: Any, learning_job: Any, cfg: Any) -> dict[str, Any]:
    tenant_id = current_tenant_id()
    enricher = TelegramReadModelEnricher(event_store=event_store, ttl_ms=2000, tenant_id=tenant_id)
    return {
        "poller": TelegramPoller(
            decide_fn=decide_fn,
            execute_fn=execute_fn,
            cfg=PollerConfig(poll_timeout_s=cfg.poll_timeout_s, poll_limit=cfg.poll_limit),
        ),
        "enricher": enricher,
        "processor": TelegramUpdateProcessor(
            decide_fn=decide_fn,
            execute_fn=execute_fn,
            enricher=enricher,
            event_log=event_log,
            product_context=dict(load_product_from_env()),
        ),
        "reconcile": PaymentsReconcileLoop(
            decide_fn=decide_fn,
            execute_fn=execute_fn,
            cfg=ReconcileConfig(every_s=cfg.reconcile_every_s),
        ),
        "payment_jobs": PaymentJobsLoop(
            decide_fn=decide_fn,
            execute_fn=execute_fn,
            payment_outbox=payment_outbox,
            cfg=PaymentJobsConfig(
                every_ms=env_ms("PAYMENT_JOBS_EVERY_S", 1.0, 200, 10_000),
                retry_after_ms=env_ms("PAYMENT_JOB_RETRY_AFTER_S", 10.0, 1000, 300_000),
                max_attempts=_bounded_int("PAYMENT_JOB_MAX_ATTEMPTS", 10, 1, 50),
            ),
        ),
        "ml": MLLearningLoop(
            learning_job=learning_job,
            cfg=MLLooopConfig(
                enabled=bool(cfg.ml_enabled),
                train_every_s=cfg.ml_train_every_s,
                monitor_every_s=cfg.ml_monitor_every_s,
            ),
        ),
        "offer_outcome": OfferOutcomeLoop(
            decide_fn=decide_fn,
            execute_fn=execute_fn,
            event_store=event_store,
            cfg=OfferOutcomeConfig(
                every_ms=_bounded_int("OFFER_OUTCOME_EVERY_MS", 60_000, 5_000, 300_000),
                timeout_ms=env_hours("OFFER_OUTCOME_TIMEOUT_H", 6, 1, 72) * 3600 * 1000,
                lookback_ms=env_hours("OFFER_OUTCOME_LOOKBACK_H", 168, 6, 24 * 30) * 3600 * 1000,
                max_emits_per_tick=_bounded_int("OFFER_OUTCOME_MAX_EMITS", 20, 1, 200),
            ),
        ),
    }
