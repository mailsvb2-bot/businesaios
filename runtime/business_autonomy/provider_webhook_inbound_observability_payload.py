from __future__ import annotations

from typing import Any, Mapping

CANON_PROVIDER_WEBHOOK_INBOUND_OBSERVABILITY_PAYLOAD = True


def build_webhook_inbound_handoff_labels(
    *,
    provider_key: str,
    status: str,
    inbound_summary: Mapping[str, Any] | None,
) -> dict[str, str]:
    summary = dict(inbound_summary or {})
    return {
        'provider_key': str(provider_key),
        'status': str(status),
        'channel': str(summary.get('channel') or ''),
        'accepted': 'true' if bool(summary.get('accepted')) else 'false',
    }


def build_webhook_inbound_handoff_rate_labels(
    *,
    provider_key: str,
    inbound_summary: Mapping[str, Any] | None,
) -> dict[str, str]:
    summary = dict(inbound_summary or {})
    return {
        'provider_key': str(provider_key),
        'channel': str(summary.get('channel') or ''),
    }


__all__ = [
    'CANON_PROVIDER_WEBHOOK_INBOUND_OBSERVABILITY_PAYLOAD',
    'build_webhook_inbound_handoff_labels',
    'build_webhook_inbound_handoff_rate_labels',
]
