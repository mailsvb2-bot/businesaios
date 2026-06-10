from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Optional, Sequence

from compliance.base import ComplianceControl, ComplianceValidationError, PolicyMetadata
from compliance.evidence_export_contract import (
    EvidenceExporter,
    EvidenceExportFormat,
    EvidenceExportManifest,
    EvidenceExportRequest,
    EvidenceExportResult,
    EvidenceRecord,
)
from compliance.pii_guard import PIIGuard


class InMemoryEvidenceExporter(EvidenceExporter):
    def __init__(
        self,
        pii_guard: Optional[PIIGuard] = None,
        *,
        policy_version: str = '2.0',
    ) -> None:
        self._pii_guard = pii_guard or PIIGuard()
        self._policy = PolicyMetadata(
            policy_name='evidence_export_service',
            policy_version=policy_version,
            tags=('evidence', 'export'),
        )

    def export(self, request: EvidenceExportRequest, records: Sequence[EvidenceRecord]) -> EvidenceExportResult:
        normalized = [
            self._normalize_record(record, include_pii=request.include_pii, redact_secrets=request.redact_secrets)
            for record in records
        ]

        if request.export_format == EvidenceExportFormat.JSON:
            payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
            content_type = 'application/json'
        elif request.export_format == EvidenceExportFormat.JSONL:
            payload = ('\n'.join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in normalized)).encode('utf-8')
            content_type = 'application/x-ndjson'
        elif request.export_format == EvidenceExportFormat.CSV:
            payload = self._to_csv(normalized)
            content_type = 'text/csv'
        else:
            raise ComplianceValidationError(f'Unsupported export format: {request.export_format}')

        warnings: list[str] = []
        if not request.include_pii:
            warnings.append('PII redaction applied.')
        if request.redact_secrets:
            warnings.append('Secret redaction applied.')
        warnings.append('Export should be audit-logged by caller.')

        manifest = EvidenceExportManifest(
            request_id=request.request_id,
            export_format=request.export_format,
            content_type=content_type,
            sha256_hex=hashlib.sha256(payload).hexdigest(),
            record_count=len(normalized),
            warnings=tuple(warnings),
            policy=self._policy,
        )
        return EvidenceExportResult(
            request_id=request.request_id,
            record_count=len(normalized),
            content_type=content_type,
            payload_bytes=payload,
            audit_tags=(
                'evidence_export',
                f'scope:{request.scope}',
                f'format:{request.export_format.value}',
                ComplianceControl.EXPORT_AUDIT.value,
            ),
            warnings=tuple(warnings),
            manifest=manifest,
        )

    def _normalize_record(self, record: EvidenceRecord, *, include_pii: bool, redact_secrets: bool) -> dict[str, object]:
        payload = dict(record.payload)
        if not include_pii or redact_secrets:
            payload = self._sanitize_mapping(payload, include_pii=include_pii, redact_secrets=redact_secrets)
        return {
            'evidence_id': record.evidence_id,
            'event_type': record.event_type,
            'timestamp_iso': record.timestamp_iso,
            'tenant_id': record.tenant_id,
            'region': record.region,
            'tags': list(record.tags),
            'payload': payload,
        }

    def _sanitize_mapping(self, payload: dict[str, object], *, include_pii: bool, redact_secrets: bool) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in payload.items():
            result[key] = self._sanitize_item(key=key, value=value, include_pii=include_pii, redact_secrets=redact_secrets)
        return result

    def _sanitize_item(self, *, key: str, value: object, include_pii: bool, redact_secrets: bool) -> object:
        lowered_key = key.strip().lower()
        if isinstance(value, dict):
            return self._sanitize_mapping(value, include_pii=include_pii, redact_secrets=redact_secrets)
        if isinstance(value, list):
            return [
                self._sanitize_item(key=key, value=item, include_pii=include_pii, redact_secrets=redact_secrets)
                for item in value
            ]
        if isinstance(value, str):
            if redact_secrets and lowered_key in {'token', 'secret', 'password', 'api_key', 'private_key', 'access_token'}:
                return '[REDACTED_SECRET]'
            text = value
            if not include_pii:
                pii_scan = self._pii_guard.inspect(text)
                if pii_scan.contains_pii:
                    text = pii_scan.redact(text)
            if redact_secrets:
                secret_scan = self._pii_guard.inspect(text)
                if secret_scan.contains_pii:
                    text = secret_scan.redact(text, replacement='[REDACTED_SECRET]')
            return text
        return value

    @staticmethod
    def _to_csv(items: Sequence[dict[str, object]]) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['evidence_id', 'event_type', 'timestamp_iso', 'tenant_id', 'region', 'tags', 'payload_json'])
        for item in items:
            writer.writerow(
                [
                    InMemoryEvidenceExporter._csv_safe(str(item['evidence_id'])),
                    InMemoryEvidenceExporter._csv_safe(str(item['event_type'])),
                    InMemoryEvidenceExporter._csv_safe(str(item['timestamp_iso'])),
                    InMemoryEvidenceExporter._csv_safe('' if item['tenant_id'] is None else str(item['tenant_id'])),
                    InMemoryEvidenceExporter._csv_safe('' if item['region'] is None else str(item['region'])),
                    InMemoryEvidenceExporter._csv_safe(','.join(item['tags'])),
                    InMemoryEvidenceExporter._csv_safe(json.dumps(item['payload'], ensure_ascii=False, sort_keys=True)),
                ]
            )
        return buffer.getvalue().encode('utf-8')

    @staticmethod
    def _csv_safe(value: str) -> str:
        if value.startswith(('=', '+', '-', '@')):
            return "'" + value
        return value


class EvidenceExportService:
    def __init__(self, exporter: Optional[EvidenceExporter] = None) -> None:
        self._exporter = exporter or InMemoryEvidenceExporter()

    def export(self, request: EvidenceExportRequest, records: Sequence[EvidenceRecord]) -> EvidenceExportResult:
        if not request.request_id.strip():
            raise ComplianceValidationError('request_id must be non-empty.')
        if not request.requester_id.strip():
            raise ComplianceValidationError('requester_id must be non-empty.')
        if not request.scope.strip():
            raise ComplianceValidationError('scope must be non-empty.')
        return self._exporter.export(request, records)
