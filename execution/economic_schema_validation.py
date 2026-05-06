from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_ECONOMIC_SCHEMA_VALIDATION = True
SUPPORTED_BUNDLE_SCHEMA_VERSION = '2'


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class EconomicSchemaValidationVerdict:
    compatible: bool
    schema_version: str
    expected_schema_version: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'compatible': bool(self.compatible),
            'schema_version': self.schema_version,
            'expected_schema_version': self.expected_schema_version,
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicSchemaValidator:
    def validate(self, *, payload: Mapping[str, Any]) -> EconomicSchemaValidationVerdict:
        normalized = _safe_dict(payload)
        manifest = _safe_dict(normalized.get('export_manifest'))
        raw_version = manifest.get('bundle_schema_version')
        schema_version = str(raw_version if raw_version not in (None, '') else '1')
        compatible = schema_version == SUPPORTED_BUNDLE_SCHEMA_VERSION
        return EconomicSchemaValidationVerdict(
            compatible=compatible,
            schema_version=schema_version,
            expected_schema_version=SUPPORTED_BUNDLE_SCHEMA_VERSION,
            reason='economic_schema_valid' if compatible else 'economic_schema_incompatible',
            metadata={'owner': 'execution.economic_schema_validation'},
        )


__all__ = [
    'CANON_ECONOMIC_SCHEMA_VALIDATION',
    'SUPPORTED_BUNDLE_SCHEMA_VERSION',
    'EconomicSchemaValidationVerdict',
    'EconomicSchemaValidator',
]
