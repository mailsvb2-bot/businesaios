from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_ECONOMIC_SCHEMA_MIGRATION_MATRIX = True
CURRENT_ECONOMIC_BUNDLE_SCHEMA_VERSION = '2'


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class EconomicSchemaMigrationVerdict:
    supported: bool
    source_version: str
    target_version: str
    migration_required: bool
    migration_kind: str
    reason: str
    allowed_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'supported': bool(self.supported),
            'source_version': self.source_version,
            'target_version': self.target_version,
            'migration_required': bool(self.migration_required),
            'migration_kind': self.migration_kind,
            'reason': self.reason,
            'allowed_path': list(self.allowed_path),
            'metadata': dict(self.metadata),
        }


class EconomicSchemaMigrationMatrix:
    """
    Read-only compatibility matrix.

    Important:
    - Does not migrate business state by itself.
    - Does not create a second planner or decision owner.
    - Only classifies whether a bundle schema version is import-compatible.
    """

    _PATHS: dict[tuple[str, str], tuple[str, ...]] = {
        ('1', '1'): ('1',),
        ('2', '2'): ('2',),
        ('1', '2'): ('1', '2'),
    }

    def validate(
        self,
        *,
        bundle_payload: Mapping[str, Any],
        runtime_target_version: str = CURRENT_ECONOMIC_BUNDLE_SCHEMA_VERSION,
    ) -> EconomicSchemaMigrationVerdict:
        manifest = _safe_dict(_safe_dict(bundle_payload).get('export_manifest'))
        source_version = _text(manifest.get('bundle_schema_version')) or '1'
        target_version = _text(runtime_target_version) or CURRENT_ECONOMIC_BUNDLE_SCHEMA_VERSION
        path = self._PATHS.get((source_version, target_version), ())
        supported = bool(path)
        migration_required = supported and source_version != target_version
        if not supported and source_version > target_version:
            reason = 'economic_schema_downgrade_forbidden'
            kind = 'downgrade_forbidden'
        elif not supported:
            reason = 'economic_schema_migration_unsupported'
            kind = 'unsupported'
        elif migration_required:
            reason = 'economic_schema_migration_required'
            kind = 'upgrade'
        else:
            reason = 'economic_schema_migration_not_required'
            kind = 'none'
        return EconomicSchemaMigrationVerdict(
            supported=supported,
            source_version=source_version,
            target_version=target_version,
            migration_required=migration_required,
            migration_kind=kind,
            reason=reason,
            allowed_path=tuple(path),
            metadata={'owner': 'execution.economic_schema_migration_matrix'},
        )


__all__ = [
    'CANON_ECONOMIC_SCHEMA_MIGRATION_MATRIX',
    'CURRENT_ECONOMIC_BUNDLE_SCHEMA_VERSION',
    'EconomicSchemaMigrationVerdict',
    'EconomicSchemaMigrationMatrix',
]
