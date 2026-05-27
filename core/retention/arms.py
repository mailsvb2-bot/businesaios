from __future__ import annotations

import json
import random
from typing import Any, Dict, Optional

from config.retention_arms_policy import DEFAULT_RETENTION_ARMS_POLICY, RetentionArmsPolicy
from core.observability.throttled_logger import exception_throttled
from core.retention.config.ai_limits import LIMITS, is_allowed_arm
from core.retention.config.offer_catalog import OFFERS
from core.retention.config.pricing_ladder import (
    WINDOWS,
    window_for_arm,
)
from core.retention.config.pricing_ladder import (
    base_price_for_arm as ladder_base_price_for_arm,
)
from core.retention.ports import RetentionStore


def choose_arm_event_sourced(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    arms: list[tuple[str, float]],
    now_ms: int,
    policy: RetentionArmsPolicy = DEFAULT_RETENTION_ARMS_POLICY,
) -> str:
    if not arms:
        return str(policy.fallback_arm)
    start_ms = int(now_ms) - int(policy.bandit_lookback_days) * int(policy.millis_per_day)
    succ: dict[str, int] = {}
    fail: dict[str, int] = {}
    for e in store.iter_events(
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=now_ms,
        user_id=user_id,
    ):
        if str(e.get("event_type")) != "offer_outcome":
            continue
        payload = _coerce_payload(e.get("payload"))
        arm = str(payload.get("arm") or payload.get("offer_arm") or "")
        if not arm:
            continue
        success = payload.get("success")
        if success is True:
            succ[arm] = succ.get(arm, 0) + 1
        elif success is False:
            fail[arm] = fail.get(arm, 0) + 1
    best_arm = arms[0][0]
    best_score = float(policy.selection_score_floor)
    for arm, profit in arms:
        store.bandit_ensure_arm(tenant_id=tenant_id, arm=arm, now_ms=now_ms)
        a, b = store.bandit_get_arm(tenant_id=tenant_id, arm=arm)
        if arm in succ or arm in fail:
            a = 1 + int(succ.get(arm, 0))
            b = 1 + int(fail.get(arm, 0))
        theta = random.betavariate(float(a), float(b))
        score = float(theta) * float(profit)
        if score > best_score:
            best_score = score
            best_arm = arm
    return best_arm


def arm_already_shown_in_window(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    arm: str,
    window_day_from: int,
    window_day_to: int,
    now_ms: int,
    logger=None,
    policy: RetentionArmsPolicy = DEFAULT_RETENTION_ARMS_POLICY,
) -> bool:
    lookback_days = max(1, int(window_day_to) - int(window_day_from) + 1)
    start_ms = int(now_ms) - lookback_days * int(policy.millis_per_day)
    for e in store.iter_events(
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=now_ms,
        user_id=user_id,
    ):
        if str(e.get("event_type")) != "offer_shown":
            continue
        payload = _coerce_payload(e.get("payload"))
        if str(payload.get("arm") or "") != str(arm):
            continue
        di = payload.get("day_index")
        if di is not None:
            try:
                di_i = int(di)
                if int(window_day_from) <= di_i <= int(window_day_to):
                    return True
            except Exception:
                if logger is not None:
                    exception_throttled(
                        logger,
                        key=f"retention.day_index.parse|{tenant_id}|{user_id}",
                        msg="retention: failed to parse payload.day_index",
                    )
        try:
            ts = int(e.get("timestamp_ms") or 0)
            if ts and (now_ms - ts) <= (lookback_days * int(policy.millis_per_day)):
                return True
        except Exception:
            if logger is not None:
                exception_throttled(
                    logger,
                    key=f"retention.offer_shown.ts|{tenant_id}|{user_id}",
                    msg="retention: failed to parse offer_shown timestamp_ms",
                )
    return False


def build_candidates(
    *,
    day_index: int,
    prices: Optional[dict] = None,
    policy: RetentionArmsPolicy = DEFAULT_RETENTION_ARMS_POLICY,
) -> tuple[list[tuple[str, float]], Optional[int]]:
    candidates: list[tuple[str, float]] = []
    w30 = WINDOWS.get("offer_30")
    if w30 and w30.day_from <= day_index <= w30.day_to:
        candidates.append((str(policy.offer_30_arm), float(policy.default_candidate_weight)))
    wbundle = WINDOWS.get("offer_bundle")
    if wbundle and wbundle.day_from <= day_index <= wbundle.day_to:
        candidates.append((str(policy.offer_bundle_arm), float(policy.default_candidate_weight)))
    w90 = WINDOWS.get("offer_90")
    if w90 and w90.day_from <= day_index <= w90.day_to:
        candidates.append((str(policy.offer_90_arm), float(policy.default_candidate_weight)))
    candidates = [(a, w) for a, w in candidates if is_allowed_arm(a)]
    return candidates, None


def base_price_for_arm(offer_arm: str, prices: Optional[Dict[str, Any]] = None) -> Optional[int]:
    canonical = ladder_base_price_for_arm(str(offer_arm), prices=prices)
    if canonical is not None:
        return canonical
    return {
        "offer_30_14900": int((prices or {}).get("p30", OFFERS["offer_30"].base_price_rub)),
        "offer_90_21900": int((prices or {}).get("p90", OFFERS["offer_90"].base_price_rub)),
        "offer_bundle_14_30": int((prices or {}).get("bundle_14_30", OFFERS["bundle_14_30"].base_price_rub)),
    }.get(str(offer_arm))


def filter_candidate_arms(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    candidates: list[tuple[str, float]],
    now_ms: int,
    debug: Dict[str, Any],
    logger=None,
    policy: RetentionArmsPolicy = DEFAULT_RETENTION_ARMS_POLICY,
) -> list[tuple[str, float]]:
    filtered: list[tuple[str, float]] = []
    for arm, weight in candidates:
        win = window_for_arm(str(arm))
        if not win:
            filtered.append((arm, weight))
            continue
        if arm_already_shown_in_window(
            store,
            tenant_id=tenant_id,
            user_id=user_id,
            arm=arm,
            window_day_from=int(win.day_from),
            window_day_to=int(win.day_to),
            now_ms=now_ms,
            logger=logger,
            policy=policy,
        ):
            debug.setdefault("anti_spam", {})[arm] = "already_shown_in_window"
            continue
        filtered.append((arm, weight))
    return filtered


def _coerce_payload(payload: Any) -> Dict[str, Any]:
    p = payload or {}
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except Exception:
            p = {}
    if not isinstance(p, dict):
        return {}
    return p
