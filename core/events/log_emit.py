from __future__ import annotations

from core.events.event_types import is_known, normalize_event_type
from config.env_flags import env_bool


def normalize_and_validate_event_type(event_type: str) -> str:
    et = normalize_event_type(event_type)
    if not et:
        raise ValueError("EMPTY_EVENT_TYPE")
    strict = env_bool("PRODUCTION_STRICT_EVENTS", False)
    if strict and not is_known(et):
        raise ValueError(f"UNKNOWN_EVENT_TYPE:{et}")
    return str(et)
