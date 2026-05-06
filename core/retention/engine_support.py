from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from config.env_flags import env_float, env_int
from config.pricing_retention_policy import (
    DEFAULT_RETENTION_ENGINE_POLICY,
    RetentionEnginePolicy,
)
from core.observability.throttled_logger import exception_throttled
from core.retention.ports import RetentionStore

logger = logging.getLogger(__name__)


def env_int_safe(name: str, default: int) -> int:
    try:
        return env_int(name, default)
    except Exception:
        return int(default)


def env_float_safe(name: str, default: float) -> float:
    try:
        return env_float(name, default)
    except Exception:
        return float(default)


def build_sandbox_suppressed_decision(
    *,
    tenant_id: str,
    day_key: str,
    day_index: int,
    policy: RetentionEnginePolicy = DEFAULT_RETENTION_ENGINE_POLICY,
) -> Dict[str, Any]:
    return {
        "tenant_id": str(tenant_id),
        "day_key": str(day_key),
        "day_index": int(day_index),
        "hazard": float(policy.sandbox_hazard),
        "readiness": float(policy.sandbox_readiness),
        "offer_arm": "NONE",
        "offer_price_rub": None,
        "suppressed": True,
        "reason": "sandbox",
        "debug": {"sandbox": True},
    }


def is_retention_allowed(*, tenant_id: str, user_id: str, fallback_allow: bool) -> bool:
    try:
        from core.retention.sandbox import retention_is_allowed

        return bool(retention_is_allowed(str(user_id)))
    except Exception:
        mode = "allow" if fallback_allow else "deny"
        exception_throttled(
            logger,
            key=f"retention.sandbox.helper|{tenant_id}|{user_id}|{mode}",
            msg=f"retention: sandbox helper failed (fallback {mode})",
        )
        return bool(fallback_allow)


def parse_decide_offer_context(context: dict) -> Tuple[str, int, Optional[int]]:
    try:
        day_key = str(context.get("day_key") or "day:today")
    except Exception:
        day_key = "day:today"
    try:
        day_index = int(context.get("day_index") or 0)
    except Exception:
        day_index = 0
    try:
        raw_now_ms = context.get("now_ms")
        now_ms = int(raw_now_ms) if raw_now_ms is not None else None
    except Exception:
        now_ms = None
    return day_key, day_index, now_ms


def has_active_entitlement(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    now_ms: int,
    entitlements: Optional[dict],
) -> bool:
    if isinstance(entitlements, dict):
        for value in entitlements.values():
            try:
                if isinstance(value, dict) and int(value.get("ends_at_ms") or 0) > now_ms:
                    return True
            except Exception:
                exception_throttled(
                    logger,
                    key=f"retention.entitlements.ends_at_ms|{tenant_id}|{user_id}",
                    msg="retention: failed to parse entitlements ends_at_ms",
                )
    for event in store.latest_events(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type="entitlement_granted",
        limit=20,
    ):
        payload = event.get("payload") or {}
        if isinstance(payload, str):
            try:
                import json as _json

                payload = _json.loads(payload)
            except Exception:
                payload = {}
        if isinstance(payload, dict):
            try:
                if int(payload.get("ends_at_ms") or 0) > now_ms:
                    return True
            except Exception:
                exception_throttled(
                    logger,
                    key=f"retention.entitlement_granted.ends_at_ms|{tenant_id}|{user_id}",
                    msg="retention: failed to parse entitlement_granted payload ends_at_ms",
                )
    return False


def is_outbound_overloaded(
    outbound_telemetry: Optional[dict],
    policy: RetentionEnginePolicy = DEFAULT_RETENTION_ENGINE_POLICY,
) -> bool:
    if not isinstance(outbound_telemetry, dict):
        return False
    try:
        qsize = int(outbound_telemetry.get("qsize") or outbound_telemetry.get("queue_size") or 0)
    except Exception:
        qsize = 0
    try:
        p90_wait = float(
            outbound_telemetry.get("p90_wait_ms")
            or outbound_telemetry.get("wait_p90_ms")
            or policy.sandbox_hazard
        )
    except Exception:
        p90_wait = float(policy.sandbox_hazard)
    return (
        qsize and qsize >= int(policy.outbound_queue_size_threshold)
    ) or (
        p90_wait and p90_wait >= float(policy.outbound_wait_p90_threshold_ms)
    )


def daily_offer_cap_reached(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    day_key: str,
    now_ms: int,
    policy: RetentionEnginePolicy = DEFAULT_RETENTION_ENGINE_POLICY,
) -> bool:
    cap = env_int_safe("OFFER_DAILY_CAP", int(policy.daily_offer_cap_default))
    if cap <= 0:
        return False
    shown = 0
    for event in store.latest_events(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type="offer_shown",
        limit=int(policy.shown_events_scan_limit),
    ):
        try:
            payload = event.get("payload") or {}
            if isinstance(payload, str):
                import json as _json

                payload = _json.loads(payload)
            if isinstance(payload, dict):
                if str(payload.get("day_key") or "") == str(day_key):
                    shown += 1
                else:
                    ts = int(event.get("timestamp_ms") or 0)
                    if ts and (now_ms - ts) <= int(policy.shown_event_window_ms):
                        shown += 1
        except Exception:
            continue
        if shown >= cap:
            return True
    return False
