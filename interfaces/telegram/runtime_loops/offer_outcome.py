from __future__ import annotations

"""Offer outcome emitter loop.

Purpose:
- make marketing bandit / pricing learning event-sourced even when users do nothing after an offer;
- after a timeout, emit offer_outcome(success=False) for each offer_shown without payment;
- if payment is observed after showing the offer, emit offer_outcome(success=True).

Invariants:
- no direct event writes here; we always go through DecisionCore + RuntimeExecutor;
- no network imports.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List
from collections.abc import Iterable

from core.observability.silent import swallow
from interfaces.telegram.runtime.telegram_runtime_worldstate_builder import build_system_world_state


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _env_str(name: str, default: str) -> str:
    return str(os.getenv(name, default) or default)


@dataclass
class OfferOutcomeConfig:
    every_ms: int = 60_000
    timeout_ms: int = 6 * 3600 * 1000
    lookback_ms: int = 7 * 24 * 3600 * 1000
    max_emits_per_tick: int = 20


class OfferOutcomeLoop:
    def __init__(self, *, decide_fn: Any, execute_fn: Any, event_store: Any, cfg: OfferOutcomeConfig):
        self._decide = decide_fn
        self._execute = execute_fn
        self._store = event_store
        self._cfg = cfg
        self._last_ms: int = 0
        from core.tenancy.tenant import current_tenant_id
        self._tenant_id = current_tenant_id()

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _iter(self, *, start_ms: int, end_ms: int, event_type: str) -> Iterable[dict[str, Any]]:
        """Iterator wrapper around event_store (strict tenant contract)."""
        return self._store.iter_events(tenant_id=self._tenant_id, start_ms=start_ms, end_ms=end_ms, event_type=event_type)

    def _payment_status_after(self, *, user_id: str, shown_at_ms: int, end_ms: int) -> str | None:
        """Return observed payment status after showing an offer.

        Order of precedence:
        - success (captured/succeeded) wins over failure
        - otherwise failure if a payment_failed is observed
        """
        for et in ("payment_captured", "payment_succeeded"):
            for ev in self._iter(start_ms=shown_at_ms, end_ms=end_ms, event_type=et) or []:
                try:
                    if str(ev.get("user_id") or "") == str(user_id):
                        return "paid"
                except Exception:
                    continue

        for et in ("payment_failed",):
            for ev in self._iter(start_ms=shown_at_ms, end_ms=end_ms, event_type=et) or []:
                try:
                    if str(ev.get("user_id") or "") == str(user_id):
                        return "failed"
                except Exception:
                    continue

        return None

    def tick(self) -> None:
        if not _env_bool("OFFER_OUTCOME_EMIT_ENABLED", True):
            return

        now_ms = self._now_ms()
        if (now_ms - self._last_ms) < int(self._cfg.every_ms):
            return
        self._last_ms = now_ms

        start_ms = max(0, now_ms - int(self._cfg.lookback_ms))

        shown: list[dict[str, Any]] = []
        for ev in self._iter(start_ms=start_ms, end_ms=now_ms, event_type="offer_shown") or []:
            if not isinstance(ev, dict):
                continue
            shown.append(ev)

        if not shown:
            return

        done: set[str] = set()
        for ev in self._iter(start_ms=start_ms, end_ms=now_ms, event_type="offer_outcome") or []:
            if not isinstance(ev, dict):
                continue
            payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            sid = str(payload.get("shown_event_id") or "").strip()
            if sid:
                done.add(sid)

        emits = 0
        shown.sort(key=lambda e: int(e.get("timestamp_ms") or 0))

        for ev in shown:
            if emits >= int(self._cfg.max_emits_per_tick):
                break

            shown_event_id = str(ev.get("event_id") or "").strip()
            if not shown_event_id or shown_event_id in done:
                continue

            user_id = str(ev.get("user_id") or "").strip()
            ts = int(ev.get("timestamp_ms") or 0)
            payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            arm = str(payload.get("arm") or "").strip()
            price_rub = payload.get("price_rub")
            if not user_id or not arm or ts <= 0:
                continue

            status = self._payment_status_after(user_id=user_id, shown_at_ms=ts, end_ms=now_ms)
            paid = status == "paid"
            failed = status == "failed"
            timed_out = (now_ms - ts) >= int(self._cfg.timeout_ms)

            if (not paid) and (not failed) and (not timed_out):
                continue

            job = {
                "shown_event_id": shown_event_id,
                "user_id": user_id,
                "arm": arm,
                "price_rub": price_rub,
                "shown_at_ms": ts,
                "decided_at_ms": now_ms,
                "conversion_latency_ms": int(max(0, now_ms - ts)),
                "success": bool(paid),
                "reason": ("paid" if paid else ("payment_failed" if failed else "timeout")),
            }

            try:
                from core.retention.telemetry import with_retention_telemetry

                job = with_retention_telemetry(job, user_id=user_id)
            except Exception:
                swallow(__name__, "interfaces/telegram/runtime_loops/offer_outcome.py")

            try:
                ws = build_system_world_state(
                    purpose="offer_outcome_emit",
                    meta={"job": job},
                    user_timezone=_env_str("SYSTEM_TZ", "Europe/Amsterdam"),
                    now_ms=now_ms,
                )
                env = self._decide(ws)
                self._execute(env)
                emits += 1
                done.add(shown_event_id)
            except Exception:
                continue
