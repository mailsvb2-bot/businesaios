from __future__ import annotations

"""Telegram ingress pipeline.

Single canonical ingress path for Telegram updates:
parse -> dedupe -> rate limit -> enrich -> worldstate -> decide -> execute
"""

import time
from typing import Any

from core.behavior.behavioral_state_builder import BehavioralStateBuilder
from core.observability.perf import Span
from interfaces.telegram.parsing.telegram_context import build_context
from interfaces.telegram.pipeline.ingress_dedupe import is_duplicate
from interfaces.telegram.pipeline.ingress_warning import emit_ingress_warning
from interfaces.telegram.pipeline.rate_limit import PerChatTokenBucket, TTLSeenSet
from interfaces.telegram.pipeline.update_helpers import (
    build_button_key,
    build_worldstate_with_overlays,
    emit_behavior_telemetry,
    resolve_product_context,
    run_decision_and_execution,
)
from interfaces.telegram.read_models.enricher import TelegramReadModelEnricher
from products.product_resolver import new_resolver_from_env
from runtime.platform.config.env_flags import env_float

INGRESS_WARNING_EVENT = "telegram_ingress_warning"


class TelegramUpdateProcessor:
    def __init__(
        self,
        *,
        decide_fn: Any,
        execute_fn: Any,
        enricher: TelegramReadModelEnricher,
        event_log: Any,
        product_context: dict[str, Any] | None = None,
    ):
        self._decide = decide_fn
        self._execute = execute_fn
        self._enricher = enricher
        self._event_log = event_log
        self._product_context = dict(product_context or {})
        self._product_resolver = new_resolver_from_env()
        self._behavior = BehavioralStateBuilder()

        ttl = env_float("TG_UPDATE_DEDUP_TTL_S", 120.0, lo=10.0, hi=3600.0)
        self._seen_updates = TTLSeenSet(ttl_s=ttl)

        burst = env_float("TG_RATE_BURST", 10.0, lo=1.0, hi=100.0)
        refill = env_float("TG_RATE_REFILL_PER_S", 2.0, lo=0.1, hi=50.0)
        self._bucket = PerChatTokenBucket(
            capacity=burst,
            refill_per_s=refill,
        )

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def handle_update(self, upd: dict[str, Any]) -> None:
        ctx = build_context(upd)
        if ctx is None:
            return

        button_key = build_button_key(ctx)
        ck = f"tg:{ctx.chat_id}:{int(ctx.update_id)}"
        ws = None
        try:
            with Span(
                event_log=self._event_log,
                stage="router",
                user_id=str(ctx.chat_id),
                correlation_key=str(ck),
                extra={"kind": "telegram_update", "button_key": button_key, "callback_data": ctx.callback_data, "command": ctx.command},
            ):
                try:
                    if is_duplicate(seen_updates=self._seen_updates, update_id=int(ctx.update_id)):
                        return
                except Exception as exc:
                    emit_ingress_warning(self._event_log, user_id=str(ctx.chat_id), reason="dedupe_failed", error=exc)

                try:
                    verdict = self._bucket.allow(str(ctx.chat_id), cost=1.0)
                    if not verdict.allow:
                        try:
                            self._event_log.emit(
                                event_type="telegram_rate_limited",
                                source="telegram_ingress",
                                user_id=str(ctx.chat_id),
                                decision_id="-",
                                correlation_id="-",
                                payload={"reason": verdict.reason or "rate_limited"},
                            )
                        except Exception as exc:
                            emit_ingress_warning(self._event_log, user_id=str(ctx.chat_id), reason="rate_limit_emit_failed", error=exc)
                        return
                except Exception as exc:
                    emit_ingress_warning(self._event_log, user_id=str(ctx.chat_id), reason="rate_limit_failed", error=exc)

                enrich = self._enricher.enrich_user(chat_id=ctx.chat_id)
                resolved_product = resolve_product_context(
                    resolver=self._product_resolver,
                    ctx=ctx,
                    enrich=enrich,
                    fallback=self._product_context,
                )
                ws = build_worldstate_with_overlays(
                    event_log=self._event_log,
                    ctx=ctx,
                    enrich=enrich,
                    resolved_product=resolved_product,
                    behavior_builder=self._behavior,
                    now_ms=self._now_ms(),
                )

                try:
                    emit_behavior_telemetry(event_log=self._event_log, ctx=ctx, ws=ws)
                except Exception as exc:
                    emit_ingress_warning(self._event_log, user_id=str(ctx.chat_id), reason="behavior_telemetry_failed", error=exc)
        except Exception as exc:
            emit_ingress_warning(self._event_log, user_id=str(ctx.chat_id), reason="router_failed", error=exc)
            return

        try:
            run_decision_and_execution(
                event_log=self._event_log,
                ctx=ctx,
                ws=ws,
                button_key=button_key,
                decide_fn=self._decide,
                execute_fn=self._execute,
            )
        except Exception as exc:
            emit_ingress_warning(self._event_log, user_id=str(ctx.chat_id), reason="decision_execution_failed", error=exc)
            return
