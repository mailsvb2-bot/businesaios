from __future__ import annotations

from typing import Any, Mapping


CANON_PROVIDER_WEBHOOK_INBOUND_RESULT_SUMMARY = True


def summarize_provider_webhook_inbound_result(
    *,
    handoff: Mapping[str, Any] | None,
    inbound_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    handoff_map = dict(handoff or {})
    inbound_map = dict(inbound_result or {})
    inbound_message = dict(handoff_map.get('inbound_message') or {})
    envelope = dict(inbound_map.get('decision_envelope') or {})
    return {
        'accepted': bool(inbound_map.get('accepted', False)),
        'decision_id': str(envelope.get('decision_id') or ''),
        'channel': str(inbound_message.get('channel') or ''),
        'user_id': str(inbound_message.get('user_id') or ''),
        'correlation_id': str(inbound_message.get('correlation_id') or ''),
        'transport_message_id': str(inbound_message.get('transport_message_id') or ''),
    }


__all__ = ['CANON_PROVIDER_WEBHOOK_INBOUND_RESULT_SUMMARY', 'summarize_provider_webhook_inbound_result']
