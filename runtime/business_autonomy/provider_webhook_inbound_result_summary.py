from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANON_PROVIDER_WEBHOOK_INBOUND_RESULT_SUMMARY = True


def summarize_provider_webhook_inbound_result(
    *,
    handoff: Mapping[str, Any] | None,
    inbound_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    handoff_map = dict(handoff or {})
    inbound_map = dict(inbound_result or {})
    inbound_message = dict(handoff_map.get('inbound_message') or {})
    envelope = inbound_map.get('decision_envelope')
    # The canonical gateway returns an object with .decision.decision_id;
    # compatibility processors may return mappings or malformed diagnostics.
    # Observability must not turn a verified inbound delivery into a failure.
    decision = envelope.get('decision', envelope) if isinstance(envelope, Mapping) else getattr(envelope, 'decision', None)
    decision_id = decision.get('decision_id') if isinstance(decision, Mapping) else getattr(decision, 'decision_id', '')
    return {
        'accepted': bool(inbound_map.get('accepted', False)),
        'decision_id': str(decision_id or ''),
        'channel': str(inbound_message.get('channel') or ''),
        'user_id': str(inbound_message.get('user_id') or ''),
        'correlation_id': str(inbound_message.get('correlation_id') or ''),
        'transport_message_id': str(inbound_message.get('transport_message_id') or ''),
    }


__all__ = ['CANON_PROVIDER_WEBHOOK_INBOUND_RESULT_SUMMARY', 'summarize_provider_webhook_inbound_result']
