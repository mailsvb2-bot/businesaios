from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding
from application.business_autonomy.provider_admin_contract import ProviderDefinition


@dataclass(frozen=True)
class ProviderWebhookMessagingIngress:
    channel: str
    user_id: str
    text: str
    transport_message_id: str
    correlation_id: str


def _telegram_ingress(payload: Mapping[str, Any]) -> ProviderWebhookMessagingIngress | None:
    message = payload.get('message') if isinstance(payload.get('message'), Mapping) else {}
    if not message:
        return None
    chat = message.get('chat') if isinstance(message.get('chat'), Mapping) else {}
    user = message.get('from') if isinstance(message.get('from'), Mapping) else {}
    text = str(message.get('text') or '').strip()
    if not text:
        return None
    user_id = str(user.get('id') or chat.get('id') or '').strip()
    transport_message_id = str(message.get('message_id') or '').strip()
    correlation_id = str(payload.get('update_id') or transport_message_id or '').strip()
    if not user_id:
        return None
    return ProviderWebhookMessagingIngress(channel='telegram', user_id=user_id, text=text, transport_message_id=transport_message_id, correlation_id=correlation_id)


def _whatsapp_ingress(payload: Mapping[str, Any]) -> ProviderWebhookMessagingIngress | None:
    entries = payload.get('entry') if isinstance(payload.get('entry'), list) else []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        changes = entry.get('changes') if isinstance(entry.get('changes'), list) else []
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            value = change.get('value') if isinstance(change.get('value'), Mapping) else {}
            messages = value.get('messages') if isinstance(value.get('messages'), list) else []
            for msg in messages:
                if not isinstance(msg, Mapping):
                    continue
                text_obj = msg.get('text') if isinstance(msg.get('text'), Mapping) else {}
                text = str(text_obj.get('body') or '').strip()
                if not text:
                    continue
                user_id = str(msg.get('from') or '').strip()
                transport_message_id = str(msg.get('id') or '').strip()
                if not user_id:
                    continue
                return ProviderWebhookMessagingIngress(channel='whatsapp', user_id=user_id, text=text, transport_message_id=transport_message_id, correlation_id=transport_message_id)
    return None


def _website_ingress(payload: Mapping[str, Any]) -> ProviderWebhookMessagingIngress | None:
    text = str(payload.get('text') or payload.get('message') or '').strip()
    user_id = str(payload.get('user_id') or payload.get('session_id') or '').strip()
    if not text or not user_id:
        return None
    transport_message_id = str(payload.get('message_id') or '').strip()
    correlation_id = str(payload.get('correlation_id') or transport_message_id or user_id).strip()
    return ProviderWebhookMessagingIngress(channel='web_chat', user_id=user_id, text=text, transport_message_id=transport_message_id, correlation_id=correlation_id)


def resolve_provider_webhook_messaging_ingress(*, provider: ProviderDefinition, normalized_payload: Mapping[str, Any]) -> ProviderWebhookMessagingIngress | None:
    binding = describe_provider_messaging_binding(provider)
    if binding is None:
        return None
    if provider.provider_key == 'telegram_bot':
        return _telegram_ingress(normalized_payload)
    if provider.provider_key == 'whatsapp_cloud':
        return _whatsapp_ingress(normalized_payload)
    if provider.provider_key == 'generic_website':
        return _website_ingress(normalized_payload)
    return None


def messaging_ingress_to_metadata(ingress: ProviderWebhookMessagingIngress | None) -> dict[str, Any]:
    if ingress is None:
        return {}
    return {'channel': ingress.channel, 'user_id': ingress.user_id, 'text': ingress.text, 'transport_message_id': ingress.transport_message_id, 'correlation_id': ingress.correlation_id}


__all__ = ['ProviderWebhookMessagingIngress', 'resolve_provider_webhook_messaging_ingress', 'messaging_ingress_to_metadata']
