from __future__ import annotations

import logging
from typing import Any, Dict, Iterable

from core.observability.throttled_logger import exception_throttled

from .shared import safe_json

logger = logging.getLogger(__name__)


def apply_audio_features(*, vec: Dict[str, float], events: Iterable[Dict[str, Any]], tenant_id: str, user_id: str) -> None:
    audio_sent = [e for e in events if str(e.get("event_type")) == "audio_sent"]
    vec["audio_plays_d1"] = float(len(audio_sent))

    listen_pos_s = 0.0
    listen_total_s = 0.0
    completed = 0
    started = 0

    for event in events:
        event_type = str(event.get("event_type") or "")
        if event_type == "audio_started":
            started += 1
            payload = safe_json(event.get("payload"))
            for key in ("total_s", "duration_s", "total_seconds", "duration_seconds"):
                if key in payload:
                    try:
                        listen_total_s = max(listen_total_s, float(payload[key]))
                    except Exception:
                        exception_throttled(logger, key=f'retention.feature.audio_total_s|{tenant_id}|{user_id}', msg='retention: failed to parse audio total_s')
        elif event_type == "audio_progress":
            payload = safe_json(event.get("payload"))
            for key in ("pos_s", "position_s", "listened_s", "seconds", "played_s"):
                if key in payload:
                    try:
                        listen_pos_s = max(listen_pos_s, float(payload[key]))
                    except Exception:
                        exception_throttled(logger, key=f'retention.feature.audio_pos_s|{tenant_id}|{user_id}', msg='retention: failed to parse audio pos_s')
            for key in ("total_s", "duration_s", "total_seconds", "duration_seconds"):
                if key in payload:
                    try:
                        listen_total_s = max(listen_total_s, float(payload[key]))
                    except Exception:
                        exception_throttled(logger, key=f'retention.feature.audio_total_s|{tenant_id}|{user_id}', msg='retention: failed to parse audio total_s')
        elif event_type == "audio_completed":
            completed += 1
            payload = safe_json(event.get("payload"))
            for key in ("total_s", "duration_s", "total_seconds", "duration_seconds"):
                if key in payload:
                    try:
                        listen_total_s = max(listen_total_s, float(payload[key]))
                    except Exception:
                        exception_throttled(logger, key=f'retention.feature.audio_total_s|{tenant_id}|{user_id}', msg='retention: failed to parse audio total_s')

    if completed > 0:
        vec["audio_completed_d1"] = float(completed)
    if started > 0:
        vec["audio_started_d1"] = float(started)

    vec["listen_seconds_d1"] = float(max(0.0, listen_pos_s))
    if listen_total_s > 1.0:
        vec["listen_ratio_d1"] = float(max(0.0, min(listen_pos_s / listen_total_s, 1.0)))
    elif completed > 0:
        vec["listen_ratio_d1"] = 1.0
    else:
        vec["listen_ratio_d1"] = 0.0
