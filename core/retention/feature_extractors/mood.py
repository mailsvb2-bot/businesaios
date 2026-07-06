from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from config.retention_mood_policy import (
    DEFAULT_RETENTION_MOOD_POLICY,
    RetentionMoodPolicy,
)
from core.observability.throttled_logger import exception_throttled

from .shared import safe_json

logger = logging.getLogger(__name__)


def mood10_to_bucket(mood_0_10: float, *, policy: RetentionMoodPolicy | None = None) -> int:
    policy = policy or DEFAULT_RETENTION_MOOD_POLICY
    m = float(mood_0_10)
    if m <= float(policy.calm_upper_inclusive):
        return 1
    if m <= float(policy.tense_upper_inclusive):
        return 2
    if m <= float(policy.heavy_upper_inclusive):
        return 3
    return 4


def apply_mood_features(
    *,
    vec: dict[str, float],
    events: Iterable[dict[str, Any]],
    store: Any,
    tenant_id: str,
    user_id: str,
    policy: RetentionMoodPolicy | None = None,
) -> None:
    policy = policy or DEFAULT_RETENTION_MOOD_POLICY
    moods_today: list[float] = []
    for event in events:
        if str(event.get("event_type")) != "mood_logged":
            continue
        payload = safe_json(event.get("payload"))
        if "mood" in payload:
            try:
                moods_today.append(float(payload["mood"]))
            except Exception:
                exception_throttled(logger, key=f'retention.feature.mood.parse|{tenant_id}|{user_id}', msg='retention: failed to parse mood_today')

    if moods_today:
        bucket = mood10_to_bucket(moods_today[-1], policy=policy)
        vec["mood_today"] = float(bucket)
        vec["mood_latest_0_10"] = float(max(float(policy.mood_min), min(moods_today[-1], float(policy.mood_max))))

    last_moods: list[int] = []
    for event in store.latest_events(tenant_id=tenant_id, user_id=user_id, event_type="mood_logged", limit=int(policy.latest_events_limit)):
        payload = safe_json(event.get("payload"))
        if "mood" in payload:
            try:
                last_moods.append(mood10_to_bucket(float(payload["mood"]), policy=policy))
            except Exception:
                exception_throttled(logger, key=f'retention.feature.mood_d7.parse|{tenant_id}|{user_id}', msg='retention: failed to parse mood_d7')

    if last_moods:
        n = len(last_moods)
        vec["mood_mean_d7"] = float(sum(last_moods) / n)
        vec["calm_share_d7"] = float(sum(1 for m in last_moods if m == 1) / n)
        vec["tense_share_d7"] = float(sum(1 for m in last_moods if m == 2) / n)
        vec["heavy_share_d7"] = float(sum(1 for m in last_moods if m == 3) / n)
        vec["empty_share_d7"] = float(sum(1 for m in last_moods if m == 4) / n)
