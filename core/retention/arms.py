from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from config.retention_arms_policy import DEFAULT_RETENTION_ARMS_POLICY, RetentionArmsPolicy
from core.observability.throttled_logger import exception_throttled
from core.retention.config.ai_limits import is_allowed_arm
from core.retention.config.offer_catalog import OFFERS
from core.retention.config.pricing_ladder import WINDOWS, window_for_arm
from core.retention.config.pricing_ladder import (
    base_price_for_arm as ladder_base_price_for_arm,
)
from core.retention.ports import RetentionStore


@dataclass(frozen=True)
class RetentionArmEvidence:
    """Read-only evidence for one eligible retention arm.

    The object carries no final choice. DecisionCore ranks proposals built from
    these evidence rows.
    """

    arm: str
    profit_weight: float
    alpha: float
    beta: float
    posterior_mean: float
    expected_value: float
    successes: int
    failures: int
    source: str


def _positive_finite(value: Any, *, fallback: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    if not math.isfinite(number) or number <= 0.0:
        return float(fallback)
    return number


def score_arm_candidates_event_sourced(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    arms: list[tuple[str, float]],
    now_ms: int,
    policy: RetentionArmsPolicy = DEFAULT_RETENTION_ARMS_POLICY,
) -> list[RetentionArmEvidence]:
    """Build deterministic arm evidence without selecting an arm.

    Event-stream outcomes override the persisted Beta state when present, just
    as the historical implementation did. No RNG and no storage writes occur.
    """

    if not arms:
        return []
    start_ms = int(now_ms) - int(policy.bandit_lookback_days) * int(policy.millis_per_day)
    successes: dict[str, int] = {}
    failures: dict[str, int] = {}
    for event in store.iter_events(
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=now_ms,
        user_id=user_id,
    ):
        if str(event.get("event_type")) != "offer_outcome":
            continue
        payload = _coerce_payload(event.get("payload"))
        arm = str(payload.get("arm") or payload.get("offer_arm") or "")
        if not arm:
            continue
        success = payload.get("success")
        if success is True:
            successes[arm] = successes.get(arm, 0) + 1
        elif success is False:
            failures[arm] = failures.get(arm, 0) + 1

    evidence: list[RetentionArmEvidence] = []
    for arm, raw_profit in arms:
        profit = float(raw_profit)
        if not math.isfinite(profit):
            raise ValueError("retention_arm_profit_must_be_finite")
        alpha, beta = store.bandit_get_arm(tenant_id=tenant_id, arm=arm)
        source = "bandit_state"
        if arm in successes or arm in failures:
            alpha = 1 + int(successes.get(arm, 0))
            beta = 1 + int(failures.get(arm, 0))
            source = "event_stream"
        alpha_f = _positive_finite(alpha)
        beta_f = _positive_finite(beta)
        posterior = alpha_f / (alpha_f + beta_f)
        evidence.append(
            RetentionArmEvidence(
                arm=str(arm),
                profit_weight=profit,
                alpha=alpha_f,
                beta=beta_f,
                posterior_mean=float(posterior),
                expected_value=float(posterior * profit),
                successes=int(successes.get(arm, 0)),
                failures=int(failures.get(arm, 0)),
                source=source,
            )
        )
    return evidence


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
    for event in store.iter_events(
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=now_ms,
        user_id=user_id,
    ):
        if str(event.get("event_type")) != "offer_shown":
            continue
        payload = _coerce_payload(event.get("payload"))
        if str(payload.get("arm") or "") != str(arm):
            continue
        day_index = payload.get("day_index")
        if day_index is not None:
            try:
                parsed_day_index = int(day_index)
                if int(window_day_from) <= parsed_day_index <= int(window_day_to):
                    return True
            except (TypeError, ValueError):
                if logger is not None:
                    exception_throttled(
                        logger,
                        key=f"retention.day_index.parse|{tenant_id}|{user_id}",
                        msg="retention: failed to parse payload.day_index",
                    )
        try:
            timestamp_ms = int(event.get("timestamp_ms") or 0)
        except (TypeError, ValueError):
            if logger is not None:
                exception_throttled(
                    logger,
                    key=f"retention.offer_shown.ts|{tenant_id}|{user_id}",
                    msg="retention: failed to parse offer_shown timestamp_ms",
                )
            continue
        if timestamp_ms and (now_ms - timestamp_ms) <= lookback_days * int(policy.millis_per_day):
            return True
    return False


def build_candidates(
    *,
    day_index: int,
    prices: dict | None = None,
    policy: RetentionArmsPolicy = DEFAULT_RETENTION_ARMS_POLICY,
) -> tuple[list[tuple[str, float]], int | None]:
    del prices
    candidates: list[tuple[str, float]] = []
    for window_key, arm in (
        ("offer_30", str(policy.offer_30_arm)),
        ("offer_bundle", str(policy.offer_bundle_arm)),
        ("offer_90", str(policy.offer_90_arm)),
    ):
        window = WINDOWS.get(window_key)
        if window and window.day_from <= day_index <= window.day_to:
            candidates.append((arm, float(policy.default_candidate_weight)))
    return [(arm, weight) for arm, weight in candidates if is_allowed_arm(arm)], None


def base_price_for_arm(offer_arm: str, prices: dict[str, Any] | None = None) -> int | None:
    canonical = ladder_base_price_for_arm(str(offer_arm), prices=prices)
    if canonical is not None:
        return canonical
    return {
        "offer_30_14900": int((prices or {}).get("p30", OFFERS["offer_30"].base_price_rub)),
        "offer_90_21900": int((prices or {}).get("p90", OFFERS["offer_90"].base_price_rub)),
        "offer_bundle_14_30": int(
            (prices or {}).get("bundle_14_30", OFFERS["bundle_14_30"].base_price_rub)
        ),
    }.get(str(offer_arm))


def filter_candidate_arms(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    candidates: list[tuple[str, float]],
    now_ms: int,
    debug: dict[str, Any],
    logger=None,
    policy: RetentionArmsPolicy = DEFAULT_RETENTION_ARMS_POLICY,
) -> list[tuple[str, float]]:
    filtered: list[tuple[str, float]] = []
    for arm, weight in candidates:
        window = window_for_arm(str(arm))
        if not window:
            filtered.append((arm, weight))
            continue
        if arm_already_shown_in_window(
            store,
            tenant_id=tenant_id,
            user_id=user_id,
            arm=arm,
            window_day_from=int(window.day_from),
            window_day_to=int(window.day_to),
            now_ms=now_ms,
            logger=logger,
            policy=policy,
        ):
            debug.setdefault("anti_spam", {})[arm] = "already_shown_in_window"
            continue
        filtered.append((arm, weight))
    return filtered


def _coerce_payload(payload: Any) -> dict[str, Any]:
    value = payload or {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            value = {}
    return value if isinstance(value, dict) else {}
