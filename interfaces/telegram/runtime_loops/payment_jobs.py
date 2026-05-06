from __future__ import annotations

"""Durable payment webhook jobs processing.

This is runner orchestration only:
- list pending outbox items
- claim
- ask DecisionCore for a decision
- execute via RuntimeExecutor
- mark delivered / retry / dead-letter
"""

import os
import logging
import time
from typing import Any, Dict

from core.tenancy.tenant import current_tenant_id
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _maybe_parse_json(v: Any) -> Any:
    """Outbox implementations may store payload as JSON string."""
    if not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return {}
    try:
        import json

        return json.loads(s)
    except Exception:
        return {}



def _normalize_webhook_job(raw: dict) -> dict:
    """Normalize multiple webhook job payload shapes to canonical fields.

    Canonical fields for policies:
      - type: 'yookassa_webhook'
      - external_id: payment id (string)
      - event: event name
      - notification_id: webhook notification id (optional)
      - raw: original payload
    """
    # Support wrapper format produced by the threaded webhook server:
    #   { type: 'yookassa_webhook', dedupe_key: '...', payload: <raw_yookassa>, received_at_ms: ... }
    if str(raw.get("type") or "").strip() == "yookassa_webhook" and isinstance(raw.get("payload"), dict):
        raw = raw.get("payload") or {}

    obj = raw.get('object') if isinstance(raw.get('object'), dict) else {}
    external_id = raw.get('external_id') or raw.get('external_payment_id') or obj.get('id')
    event = raw.get('event')
    notification_id = raw.get('notification_id') or raw.get('id')
    out = {
        'type': 'yookassa_webhook',
        'external_id': str(external_id) if external_id is not None else '',
        'event': str(event) if event is not None else '',
        'notification_id': str(notification_id) if notification_id is not None else None,
        'raw': raw.get('raw') if raw.get('raw') is not None else raw,
    }
    if not out['external_id']:
        raise ValueError('MISSING_EXTERNAL_ID')
    if not out['event']:
        raise ValueError('MISSING_EVENT')
    return out

from interfaces.telegram.runtime.telegram_runtime_worldstate_builder import build_system_world_state
from runtime.platform.config.env_flags import env_str
from core.observability.silent import swallow


@dataclass
class PaymentJobsConfig:
    every_ms: int = 1000
    retry_after_ms: int = 10_000
    max_attempts: int = 10


class PaymentJobsLoop:
    def __init__(self, *, decide_fn: Any, execute_fn: Any, payment_outbox: Any, cfg: PaymentJobsConfig):
        self._decide = decide_fn
        self._execute = execute_fn
        self._outbox = payment_outbox
        self._cfg = cfg
        self._last_ms: int = 0
        self._last_err_ms: dict[str, int] = {}

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def tick(self) -> None:
        if self._outbox is None:
            return
        now_ms = self._now_ms()
        if (now_ms - self._last_ms) < int(self._cfg.every_ms):
            return
        self._last_ms = now_ms

        items = self._outbox.list_pending(limit=20)
        for it in items or []:
            job_id = str(it.get("id")) if isinstance(it, dict) else ""
            if not job_id:
                continue
            attempts = int((it.get("attempts") or 0) if isinstance(it, dict) else 0)
            raw_payload: Any = {}
            if isinstance(it, dict):
                raw_payload = _maybe_parse_json(it.get("payload"))
            raw_payload = raw_payload if isinstance(raw_payload, dict) else {}
            # Compatibility: some outboxes store type at top-level and keep payload as raw YooKassa JSON
            if isinstance(it, dict) and str(it.get("type") or "").strip() == "yookassa_webhook":
                if not str(raw_payload.get("type") or "").strip():
                    raw_payload = {"type": "yookassa_webhook", "payload": raw_payload}
            try:
                payload = _normalize_webhook_job(raw_payload)
            except Exception as e:
                # invalid job payload: dead-letter fast
                try:
                    self._outbox.move_to_dead_letter(job_id, error=f"invalid_payload:{type(e).__name__}")
                except Exception:
                    swallow(__name__, 'interfaces/telegram/runtime_loops/payment_jobs.py')
                continue

            if attempts >= int(self._cfg.max_attempts):
                try:
                    self._outbox.move_to_dead_letter(job_id, error="max_attempts")
                except Exception:
                    swallow(__name__, 'interfaces/telegram/runtime_loops/payment_jobs.py')
                continue

            if not self._outbox.claim(job_id):
                continue

            try:
                ws = build_system_world_state(
                    purpose="payments_webhook_reconcile",
                    tenant_id=current_tenant_id(),
                    meta={"job": payload},
                    user_timezone=env_str("SYSTEM_TZ", "Europe/Amsterdam"),
                    now_ms=self._now_ms(),
                )
                env = self._decide(ws)
                self._execute(env)
                try:
                    self._outbox.mark_delivered(job_id)
                except Exception:
                    swallow(__name__, 'interfaces/telegram/runtime_loops/payment_jobs.py')
            except Exception as e:
                try:
                    self._throttled_err(f"job_failed:{job_id}", e)
                except Exception:
                    swallow(__name__, 'interfaces/telegram/runtime_loops/payment_jobs.py')
                try:
                    self._outbox.schedule_retry(job_id, after_ms=int(self._cfg.retry_after_ms), error=repr(e))
                except Exception:
                    swallow(__name__, 'interfaces/telegram/runtime_loops/payment_jobs.py')

    def _throttled_err(self, key: str, e: Exception) -> None:
        now_ms = int(time.time() * 1000)
        prev = int(self._last_err_ms.get(key, 0))
        if (now_ms - prev) < 30_000:
            return
        self._last_err_ms[key] = now_ms
        try:
            logger.exception("payment_jobs error %s: %r", key, e)
        except Exception:
            swallow(__name__, 'interfaces/telegram/runtime_loops/payment_jobs.py')