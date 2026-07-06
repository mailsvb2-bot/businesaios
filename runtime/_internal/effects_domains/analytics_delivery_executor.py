from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime._internal.effects_domains.analytics_delivery import build_analytics_webhook_effect
from runtime._internal.http_transport import sync_post_json

CANON_INTERNAL_ANALYTICS_DELIVERY_EXECUTOR = True


def execute_analytics_webhook_delivery(
    *,
    tenant_id: str,
    webhook_url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str] | None = None,
    timeout_s: int = 30,
) -> dict[str, Any]:
    effect = build_analytics_webhook_effect(
        tenant_id=str(tenant_id),
        webhook_url=str(webhook_url),
        payload=dict(payload),
    )
    response = sync_post_json(
        url=str(webhook_url),
        headers={**dict(headers or {}), 'X-BusinesAIOS-Effect-Type': 'analytics_webhook_delivery'},
        data=dict(effect['payload']),
        timeout_s=int(timeout_s),
    )
    return {
        'tenant_id': str(tenant_id),
        'effect_type': effect['effect_type'],
        'status': int(response.status),
        'ok': 200 <= int(response.status) < 300,
        'response_json': response.json,
        'response_text': response.text,
    }
