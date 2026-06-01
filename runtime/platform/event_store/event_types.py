from __future__ import annotations

from typing import Dict, Set

# Canonical vocabulary used by:
# - runtime telemetry
# - retention extractor
# - analytics
UI_CLICK = "ui_click"
PAYWALL_OPENED = "paywall_opened"
PAYWALL_CLOSED = "paywall_closed"
OFFER_SHOWN = "offer_shown"
OFFER_CLICKED = "offer_clicked"
PURCHASE_ATTEMPT = "purchase_attempt"
PURCHASE_SUCCESS = "purchase_success"
PURCHASE_FAILED = "purchase_failed"
OFFER_OUTCOME = "offer_outcome"
MOOD_LOGGED = "mood_logged"
AUDIO_SENT = "audio_sent"
AUDIO_STARTED = "audio_started"
AUDIO_PROGRESS = "audio_progress"
AUDIO_STOPPED = "audio_stopped"
AUDIO_COMPLETED = "audio_completed"
ENTITLEMENT_GRANTED = "entitlement_granted"
MESSAGE_SENT = "message_sent"
MESSAGE_FAILED = "message_failed"

KNOWN_EVENT_TYPES: set[str] = {
    UI_CLICK,
    PAYWALL_OPENED,
    PAYWALL_CLOSED,
    OFFER_SHOWN,
    OFFER_CLICKED,
    PURCHASE_ATTEMPT,
    PURCHASE_SUCCESS,
    PURCHASE_FAILED,
    OFFER_OUTCOME,
    MOOD_LOGGED,
    AUDIO_SENT,
    AUDIO_STARTED,
    AUDIO_PROGRESS,
    AUDIO_STOPPED,
    AUDIO_COMPLETED,
    ENTITLEMENT_GRANTED,
    MESSAGE_SENT,
    MESSAGE_FAILED,
}

ALIASES: dict[str, str] = {
    "paywall_open": PAYWALL_OPENED,
    "paywall_close": PAYWALL_CLOSED,
    "offer_click_primary": OFFER_CLICKED,
    "offer_click_secondary": OFFER_CLICKED,
}


def normalize_event_type(event_type: str) -> str:
    et = (event_type or "").strip()
    if not et:
        return ""
    return ALIASES.get(et, et)


def is_known(event_type: str) -> bool:
    return normalize_event_type(event_type) in KNOWN_EVENT_TYPES
