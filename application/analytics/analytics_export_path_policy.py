from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

CANON_ANALYTICS_EXPORT_SANDBOX = True
CANON_ANALYTICS_EXPORT_TENANT_ISOLATION = True
_SAFE_EXPORT_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')


def default_analytics_export_root() -> Path:
    explicit = str(os.getenv('BUSINESAIOS_ANALYTICS_EXPORT_ROOT', '') or '').strip()
    if explicit:
        return Path(explicit)
    data_dir = Path(str(os.getenv('DATA_DIR', 'data') or 'data').strip() or 'data')
    return data_dir / 'analytics_exports'


def _tenant_directory(tenant_id: str) -> str:
    normalized = str(tenant_id or '').strip()
    if not normalized:
        raise ValueError('tenant_id is required')
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]
    return f'tenant-{digest}'


def _relative_parts(value: str, *, field_name: str) -> tuple[str, ...]:
    text = str(value or '').strip().replace('\\', '/')
    if not text:
        return ()
    path = PurePosixPath(text)
    if path.is_absolute() or text.startswith('/'):
        raise ValueError(f'{field_name}_must_be_relative')
    parts = tuple(path.parts)
    if not parts or any(part in {'', '.', '..'} for part in parts):
        raise ValueError(f'{field_name}_contains_forbidden_segment')
    if any(':' in part or '\x00' in part for part in parts):
        raise ValueError(f'{field_name}_contains_forbidden_character')
    return parts


@dataclass(frozen=True)
class AnalyticsExportPathPolicy:
    export_root: Path

    @classmethod
    def default(cls) -> 'AnalyticsExportPathPolicy':
        return cls(export_root=default_analytics_export_root())

    def normalized_relative_file(self, *, requested_path: str | None, tenant_id: str) -> str:
        tenant_directory = _tenant_directory(tenant_id)
        if requested_path is None or not str(requested_path).strip():
            parts = ('analytics-dashboard-bundle.json',)
        else:
            parts = _relative_parts(str(requested_path), field_name='export_path')
            if not parts[-1].lower().endswith('.json'):
                raise ValueError('export_path_must_end_with_json')
        return '/'.join((tenant_directory, *parts))

    def resolve_file(self, *, requested_path: str | None, tenant_id: str) -> Path:
        relative = self.normalized_relative_file(requested_path=requested_path, tenant_id=tenant_id)
        root = self.export_root.expanduser().resolve()
        candidate = root.joinpath(*PurePosixPath(relative).parts).resolve()
        self._require_within_root(candidate=candidate, root=root)
        return candidate

    def resolve_directory(self, *, requested_dir: str | None, tenant_id: str) -> Path:
        tenant_directory = _tenant_directory(tenant_id)
        if requested_dir is None or not str(requested_dir).strip():
            parts: tuple[str, ...] = ()
        else:
            parts = _relative_parts(str(requested_dir), field_name='export_dir')
        root = self.export_root.expanduser().resolve()
        candidate = root.joinpath(tenant_directory, *parts).resolve()
        self._require_within_root(candidate=candidate, root=root)
        return candidate

    @staticmethod
    def validate_export_id(export_id: str) -> str:
        value = str(export_id or '').strip()
        if not _SAFE_EXPORT_ID.fullmatch(value) or value in {'.', '..'}:
            raise ValueError('invalid_export_id')
        return value

    @staticmethod
    def _require_within_root(*, candidate: Path, root: Path) -> None:
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError('analytics_export_path_outside_sandbox') from exc


__all__ = [
    'AnalyticsExportPathPolicy',
    'CANON_ANALYTICS_EXPORT_SANDBOX',
    'CANON_ANALYTICS_EXPORT_TENANT_ISOLATION',
    'default_analytics_export_root',
]
