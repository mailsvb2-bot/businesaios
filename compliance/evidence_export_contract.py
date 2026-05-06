from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Protocol, Sequence

from compliance.base import PolicyMetadata


class EvidenceExportFormat(str, Enum):
    JSON = 'json'
    JSONL = 'jsonl'
    CSV = 'csv'


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    event_type: str
    timestamp_iso: str
    payload: Mapping[str, object]
    tenant_id: Optional[str] = None
    region: Optional[str] = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceExportRequest:
    request_id: str
    export_format: EvidenceExportFormat
    requester_id: str
    scope: str
    tenant_id: Optional[str] = None
    region: Optional[str] = None
    include_pii: bool = False
    redact_secrets: bool = True
    filters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceExportManifest:
    request_id: str
    export_format: EvidenceExportFormat
    content_type: str
    sha256_hex: str
    record_count: int
    warnings: tuple[str, ...]
    policy: PolicyMetadata


@dataclass(frozen=True)
class EvidenceExportResult:
    request_id: str
    record_count: int
    content_type: str
    payload_bytes: bytes
    audit_tags: tuple[str, ...]
    warnings: tuple[str, ...]
    manifest: EvidenceExportManifest


class EvidenceExporter(Protocol):
    def export(self, request: EvidenceExportRequest, records: Sequence[EvidenceRecord]) -> EvidenceExportResult: ...
