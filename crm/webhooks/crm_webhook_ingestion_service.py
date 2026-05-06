from __future__ import annotations

from crm.webhooks.crm_webhook_dedup_store import InMemoryCrmWebhookDedupStore
from crm.webhooks.crm_webhook_event_parser import CrmWebhookEventParser
from crm.webhooks.crm_webhook_router import CrmWebhookRouter


class CrmWebhookIngestionService:
    def __init__(self, *, parser: CrmWebhookEventParser | None = None, dedup_store: InMemoryCrmWebhookDedupStore | None = None, router: CrmWebhookRouter | None = None) -> None:
        self._parser = parser or CrmWebhookEventParser()
        self._dedup_store = dedup_store or InMemoryCrmWebhookDedupStore()
        self._router = router or CrmWebhookRouter()

    def ingest(self, *, provider_key: str, payload: dict[str, object]) -> dict[str, object]:
        event = self._parser.parse(provider_key, payload)
        if not self._dedup_store.first_seen(event.event_id):
            return {'accepted': False, 'reason': 'duplicate', 'event_id': event.event_id}
        return {'accepted': True, 'event_id': event.event_id, 'route': self._router.route(event)}
