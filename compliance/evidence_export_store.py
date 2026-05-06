from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from compliance.evidence_export_contract import EvidenceExportManifest, EvidenceExportRequest, EvidenceExportResult


@dataclass(frozen=True)
class StoredEvidenceExportRecord:
    request_id: str
    stored_at_iso: str
    manifest: EvidenceExportManifest
    file_path: str


class EvidenceExportStore(Protocol):
    def persist(self, *, request: EvidenceExportRequest, result: EvidenceExportResult) -> StoredEvidenceExportRecord: ...


class JsonlEvidenceExportStore:
    """Metadata-only export store."""

    def __init__(self, root_dir: str | Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_file = self._root_dir / 'evidence_exports.jsonl'

    def persist(self, *, request: EvidenceExportRequest, result: EvidenceExportResult) -> StoredEvidenceExportRecord:
        export_filename = f'{request.request_id}.{result.manifest.export_format.value}'
        export_path = self._root_dir / export_filename
        export_path.write_bytes(result.payload_bytes)

        record = StoredEvidenceExportRecord(
            request_id=request.request_id,
            stored_at_iso=datetime.now(timezone.utc).isoformat(),
            manifest=result.manifest,
            file_path=str(export_path),
        )
        row = {
            'request_id': record.request_id,
            'stored_at_iso': record.stored_at_iso,
            'file_path': record.file_path,
            'manifest': {
                'request_id': record.manifest.request_id,
                'export_format': record.manifest.export_format.value,
                'content_type': record.manifest.content_type,
                'sha256_hex': record.manifest.sha256_hex,
                'record_count': record.manifest.record_count,
                'warnings': list(record.manifest.warnings),
                'policy': {
                    'policy_name': record.manifest.policy.policy_name,
                    'policy_version': record.manifest.policy.policy_version,
                    'tags': list(record.manifest.policy.tags),
                    'metadata': dict(record.manifest.policy.metadata),
                },
            },
        }
        with self._manifest_file.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        return record
