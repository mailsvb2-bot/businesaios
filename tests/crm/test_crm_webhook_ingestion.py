from crm.webhooks.crm_webhook_ingestion_service import CrmWebhookIngestionService


def test_webhook_ingestion_deduplicates_events():
    service = CrmWebhookIngestionService()
    assert service.ingest(provider_key='hubspot', payload={'event_id': '1', 'event_type': 'deal.created'})['accepted'] is True
    assert service.ingest(provider_key='hubspot', payload={'event_id': '1', 'event_type': 'deal.created'})['accepted'] is False
