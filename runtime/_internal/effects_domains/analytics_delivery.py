from __future__ import annotations

from typing import Any
from collections.abc import Mapping

CANON_INTERNAL_ANALYTICS_DELIVERY = True


def build_analytics_webhook_effect(*, tenant_id: str, webhook_url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "effect_type": "analytics_webhook_delivery",
        "tenant_id": str(tenant_id),
        "webhook_url": str(webhook_url),
        "payload": dict(payload),
    }
