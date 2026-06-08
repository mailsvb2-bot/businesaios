from __future__ import annotations

import logging
from typing import Any, Optional

from core.observability.errors import log_exception_throttled
from core.observability.throttled_logger import exception_throttled
from core.retention.decision_debug import build_retention_debug
from core.retention.decision_steps import make_telemetry_step, offer_allowed, render_offer_step
from core.tenancy.normalization import normalize_tenant_id

log = logging.getLogger(__name__)


def read_outbound_metrics(*, reader: Any, logger: Any) -> dict:
    try:
        return dict(reader() or {})
    except Exception:
        log_exception_throttled(logger or log, key="retention.outbound_metrics", msg="retention: outbound metrics read failed", throttle_ms=30_000)
        return {}


def read_entitlements_from_state(*, state: Any, logger: Any) -> Any:
    try:
        if isinstance(getattr(state, "economy", None), dict):
            return state.economy.get("entitlements")
    except Exception:
        log_exception_throttled(logger or log, key="retention.entitlements", msg="retention: failed to read entitlements from state.economy", throttle_ms=60_000)
    return None


def decorate_retention_payload(*, payload: dict, user_id: str, key: str, msg: str) -> dict:
    try:
        from core.retention.telemetry import with_retention_telemetry
        return with_retention_telemetry(payload, user_id=user_id)
    except Exception:
        exception_throttled(log, key=f"{key}|{user_id}", msg=msg)
        return payload


def build_initial_plan(*, decision: Any, user_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    debug = build_retention_debug(decision)
    step = make_telemetry_step(decision=decision, user_id=user_id)
    step["payload"] = decorate_retention_payload(
        payload=step["payload"],
        user_id=user_id,
        key="retention.telemetry.decorate",
        msg="retention: failed to decorate telemetry payload",
    )
    return [step], debug


def try_build_offer_step(
    *,
    decision: Any,
    state: Any,
    offer_engine: Any,
    cooldown_store: Any,
    user_id: str,
) -> tuple[dict | None, dict[str, Any] | None]:
    if decision.suppressed or not decision.offer_arm or decision.offer_arm == "NONE" or decision.offer_price_rub is None:
        return None, None

    try:
        tenant0 = normalize_tenant_id(getattr(state, "tenant_id", None), fallback=str(decision.tenant_id or "").strip())
        if not tenant0:
            dbg = dict(decision.debug or {})
            dbg.setdefault("constraints", {})["suppressed_offer"] = str(decision.offer_arm)
            dbg["constraints"]["reason"] = "missing_tenant_id"
            return None, dbg
        ok = offer_allowed(
            offer_engine=offer_engine,
            cooldown_store=cooldown_store,
            state=state,
            tenant_id=tenant0,
            user_id=user_id,
            offer_id=str(decision.offer_arm),
        )
        if not ok:
            return None, None
    except Exception:
        exception_throttled(log, key=f"retention.offer_guardrails.unavailable|{user_id}", msg="retention: offer guardrails check failed (allow)")

    try:
        pc = getattr(state, "price_constraints", None)
        max_band = (pc or {}).get("max_band") if isinstance(pc, dict) else None
        max_band = max_band.strip() if isinstance(max_band, str) else None
    except Exception:
        pc = None
        max_band = None

    try:
        if isinstance(pc, dict) and str(pc.get("mode") or "").strip().lower() == "safe":
            prefixes = pc.get("disallow_offer_prefixes")
            if isinstance(prefixes, (list, tuple)) and decision.offer_arm:
                arm = str(decision.offer_arm)
                for pfx in prefixes:
                    if isinstance(pfx, str) and arm.startswith(pfx):
                        dbg = dict(decision.debug or {})
                        dbg.setdefault("constraints", {})["suppressed_offer"] = arm
                        dbg["constraints"]["reason"] = str(pc.get("reason") or "safe_mode")
                        return None, dbg
    except Exception:
        exception_throttled(log, key=f"retention.constraints.safe_mode|{user_id}", msg="retention: failed to enforce safe_mode constraints")

    offer_step, _offer_meta = render_offer_step(
        offer_engine=offer_engine,
        state=state,
        decision=decision,
        user_id=user_id,
        max_band=max_band,
    )

    try:
        if cooldown_store is not None and hasattr(cooldown_store, "mark_shown_now"):
            cooldown_store.mark_shown_now(
                tenant_id=str(decision.tenant_id),
                user_id=str(user_id),
                offer_id=str(decision.offer_arm),
            )
    except Exception:
        exception_throttled(log, key=f"retention.cooldown.mark|{user_id}", msg="retention: failed to mark cooldown (ignored)")

    offer_step["track_payload"] = decorate_retention_payload(
        payload=offer_step["track_payload"],
        user_id=user_id,
        key="retention.telemetry.decorate_track",
        msg="retention: failed to decorate offer_shown track payload",
    )
    return offer_step, None
