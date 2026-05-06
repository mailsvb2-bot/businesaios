from compliance.evidence_export_contract import EvidenceExportFormat, EvidenceExportRequest, EvidenceRecord
from compliance.evidence_export_service import EvidenceExportService


def test_export_redacts_pii_and_secrets() -> None:
    service = EvidenceExportService()
    result = service.export(
        EvidenceExportRequest(
            request_id='req-1',
            export_format=EvidenceExportFormat.JSON,
            requester_id='user-1',
            scope='tenant_evidence',
            include_pii=False,
            redact_secrets=True,
        ),
        [
            EvidenceRecord(
                evidence_id='ev-1',
                event_type='email_sent',
                timestamp_iso='2026-03-25T10:00:00Z',
                payload={'email': 'john@example.com', 'token': 'super-secret-token'},
            )
        ],
    )
    payload = result.payload_bytes.decode('utf-8')
    assert 'john@example.com' not in payload
    assert 'super-secret-token' not in payload


def test_csv_export_hardens_formula_injection() -> None:
    service = EvidenceExportService()
    result = service.export(
        EvidenceExportRequest(
            request_id='req-2',
            export_format=EvidenceExportFormat.CSV,
            requester_id='user-1',
            scope='tenant_evidence',
        ),
        [
            EvidenceRecord(
                evidence_id='=cmd',
                event_type='+sum',
                timestamp_iso='2026-03-25T10:00:00Z',
                payload={'field': '@danger'},
            )
        ],
    )
    payload = result.payload_bytes.decode('utf-8')
    assert "'=cmd" in payload
    assert "'+sum" in payload
