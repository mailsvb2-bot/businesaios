from __future__ import annotations

from crm.webhooks.crm_webhook_contract import CrmWebhookEvent


class CrmWebhookEventParser:
    def parse(self, provider_key: str, payload: dict[str, object]) -> CrmWebhookEvent:
        return CrmWebhookEvent(provider_key=provider_key, event_type=str(payload.get('event_type') or 'unknown'), event_id=str(payload.get('event_id') or payload.get('id') or 'unknown'), payload=payload)
