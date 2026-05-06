from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_ECONOMIC_FORENSICS_CONTRACT = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class EconomicForensicsEvent:
    event_id: str
    event_type: str
    severity: str
    artifact_id: str = ''
    artifact_digest: str = ''
    tenant_id: str = ''
    business_id: str = ''
    schema_version: str = ''
    payload: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'severity': self.severity,
            'artifact_id': self.artifact_id,
            'artifact_digest': self.artifact_digest,
            'tenant_id': self.tenant_id,
            'business_id': self.business_id,
            'schema_version': self.schema_version,
            'payload': dict(self.payload),
            'tags': list(self.tags),
            'metadata': dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class EconomicForensicsExportBundle:
    bundle_id: str
    generated_at: str
    event_count: int
    integrity_sha256: str
    events: tuple[dict[str, Any], ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'bundle_id': self.bundle_id,
            'generated_at': self.generated_at,
            'event_count': int(self.event_count),
            'integrity_sha256': self.integrity_sha256,
            'events': [dict(x) for x in self.events],
            'metadata': dict(self.metadata),
        }


__all__ = [
    'CANON_ECONOMIC_FORENSICS_CONTRACT',
    'EconomicForensicsEvent',
    'EconomicForensicsExportBundle',
]
