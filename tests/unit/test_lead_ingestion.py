from leads import LeadIngestion


def test_lead_ingestion_returns_structured_result():
    result = LeadIngestion().ingest({'lead_id': 'l1'})
    assert result['kind'] == 'lead_ingestion'
