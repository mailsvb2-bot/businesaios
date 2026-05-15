from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from runtime.messaging.inbound_decision_gateway import MessagingInboundDecisionGateway
from runtime.messaging.inbound_message import InboundMessage


CANON_PROVIDER_WEBHOOK_INBOUND_PROCESSOR = True


@dataclass(frozen=True)
class ProviderWebhookInboundProcessor:
    decision_core: object

    def process(self, *, handoff: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(handoff or {}).get("inbound_message") or {}
        if not isinstance(payload, Mapping) or not payload:
            return {}
        gateway = MessagingInboundDecisionGateway(
            decision_core=self.decision_core,
            caller='runtime.business_autonomy.provider_webhook_inbound_processor',
        )
        message = InboundMessage(
            tenant_id=str(payload.get('tenant_id') or ''),
            channel=str(payload.get('channel') or ''),
            user_id=str(payload.get('user_id') or ''),
            text=str(payload.get('text') or ''),
            correlation_id=str(payload.get('correlation_id') or ''),
            transport_message_id=str(payload.get('transport_message_id') or ''),
            metadata={'source': 'provider_webhook_handoff', **dict(payload.get('metadata') or {})},
        )
        # Keep all decision issuing inside MessagingInboundDecisionGateway.  This
        # preserves the provider webhook handoff as a canonical gateway call and
        # avoids direct gateway.issue()/DecisionCore call sites in this surface.
        envelope = gateway.process(message=message) if hasattr(gateway, 'process') else gateway.issue(message=message)
        return {
            'accepted': True,
            'decision_envelope': envelope,
        }


__all__ = ['CANON_PROVIDER_WEBHOOK_INBOUND_PROCESSOR', 'ProviderWebhookInboundProcessor']
