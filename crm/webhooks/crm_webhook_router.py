from __future__ import annotations

from crm.webhooks.crm_webhook_contract import CrmWebhookEvent


class CrmWebhookRouter:
    def route(self, event: CrmWebhookEvent) -> str:
        if event.event_type.startswith('contact.'):
            return 'contact'
        if event.event_type.startswith('deal.'):
            return 'deal'
        return 'generic'
