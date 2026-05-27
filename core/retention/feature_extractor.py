from __future__ import annotations

import json
import time
from typing import Dict, Optional

from core.retention.feature_extractors.activity import apply_activity_features
from core.retention.feature_extractors.audio import apply_audio_features
from core.retention.feature_extractors.mood import apply_mood_features, mood10_to_bucket
from core.retention.feature_extractors.shared import DayWindow, day_key_from_ms, day_window_utc
from core.retention.feature_registry import ensure_complete
from core.retention.ports import RetentionStore


def compute_features_for_day(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    day_key: str,
) -> Dict[str, float]:
    """Compute (and return) a complete retention feature vector for a single UTC day."""

    window = day_window_utc(day_key)
    events = list(store.iter_events(tenant_id=tenant_id, start_ms=window.start_ms, end_ms=window.end_ms, user_id=user_id))
    vec: Dict[str, float] = {"clicks_total_d1": float(len(events))}

    apply_audio_features(vec=vec, events=events, tenant_id=tenant_id, user_id=user_id)
    apply_mood_features(vec=vec, events=events, store=store, tenant_id=tenant_id, user_id=user_id)
    apply_activity_features(vec=vec, events=events, store=store, tenant_id=tenant_id, user_id=user_id)

    return ensure_complete(vec)


def store_features_for_day(
    store: RetentionStore,
    *,
    tenant_id: str,
    user_id: str,
    day_key: str,
    features: Dict[str, float],
    now_ms: Optional[int] = None,
) -> None:
    now_ms = int(now_ms or int(time.time() * 1000))
    store.upsert_user_features_daily(
        tenant_id=tenant_id,
        user_id=user_id,
        day_key=day_key,
        features_json=json.dumps(features, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        created_at_ms=now_ms,
    )


__all__ = [
    "DayWindow",
    "compute_features_for_day",
    "day_key_from_ms",
    "day_window_utc",
    "mood10_to_bucket",
    "store_features_for_day",
]
