from __future__ import annotations

from typing import Any, Mapping

from runtime.messaging.inbound_message import InboundMessage
from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state

CANON_PROVIDER_WEBHOOK_INBOUND_HANDOFF = True


def build_provider_webhook_inbound_handoff(
    *,
    tenant_id: str,
    business_id: str,
    provider_key: str,
    messaging_ingress: Mapping[str, Any] | None,
    route_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ingress = dict(messaging_ingress or {})
    if not ingress:
        return {}

    message = InboundMessage(
        tenant_id=str(tenant_id),
        channel=str(ingress.get('channel') or ''),
        user_id=str(ingress.get('user_id') or ''),
        text=str(ingress.get('text') or ''),
        correlation_id=str(ingress.get('correlation_id') or ''),
        transport_message_id=str(ingress.get('transport_message_id') or ''),
        payload=dict(route_metadata or {}),
        metadata={
            'provider_key': str(provider_key),
            'business_id': str(business_id),
            'route_metadata': dict(route_metadata or {}),
            'source': 'provider_webhook',
        },
    )
    world_state_input = map_inbound_to_world_state(message)
    return {
        'inbound_message': {
            'tenant_id': message.tenant_id,
            'channel': message.channel,
            'user_id': message.user_id,
            'text': message.text,
            'correlation_id': message.correlation_id,
            'transport_message_id': message.transport_message_id,
            'metadata': dict(message.metadata or {}),
        },
        'world_state_input': {
            'tenant_id': world_state_input.tenant_id,
            'user_id': world_state_input.user_id,
            'channel': world_state_input.channel,
            'message_text': world_state_input.message_text,
            'correlation_id': world_state_input.correlation_id,
            'transport_message_id': world_state_input.transport_message_id,
        },
        'ingress_owner': 'runtime.messaging.inbound_entrypoint',
        'provider_key': str(provider_key),
        'business_id': str(business_id),
    }


__all__ = ['CANON_PROVIDER_WEBHOOK_INBOUND_HANDOFF', 'build_provider_webhook_inbound_handoff']
