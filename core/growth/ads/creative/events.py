from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict

from .models import CreativeSelection


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def event_creative_generated(
    *,
    tenant_id: str,
    user_id: str,
    session_id: str,
    selection: CreativeSelection,
) -> Dict[str, Any]:
    """Event payload for event_store: event_type=ads_creative_generated"""
    return {
        "schema_v": 1,
        "event_id": str(uuid.uuid4()),
        "event_type": "ads_creative_generated",
        "ts": now_utc_iso(),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_id": session_id,
        "channel": "webapp",
        "locale": "ru",
        "timezone": "UTC",
        "app_version": "ads_creative_autopilot_v1",
        "device": {"device_type": "desktop", "os_family": "Other", "ua": ""},
        "context": {"product_id": "businesaios", "product_version": "v1"},
        "idempotency_key": f"ads_creative_generated:{tenant_id}:{selection.selected.creative_id}",
        "payload": {
            "selected": asdict(selection.selected),
            "scores": selection.scores,
            "reason": selection.reason,
            "guardrails_ok": selection.guardrails_ok,
        },
    }
