from __future__ import annotations

from dataclasses import dataclass, field

from connectors.platform.connector_registry import ConnectorRegistry

CANON_CONNECTOR_VERSION_REGISTRY = True


@dataclass(frozen=True)
class ConnectorVersionRecord:
    connector_id: str
    version: str
    status: str = 'active'
    deprecated: bool = False
    replacement_version: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.connector_id or '').strip():
            raise ValueError('connector_id is required')
        if not str(self.version or '').strip():
            raise ValueError('version is required')
        if not str(self.status or '').strip():
            raise ValueError('status is required')
        if self.replacement_version is not None and not str(self.replacement_version).strip():
            raise ValueError('replacement_version must be non-empty when provided')
        if self.replacement_version is not None and str(self.replacement_version).strip() == str(self.version).strip():
            raise ValueError('replacement_version must differ from version')


class ConnectorVersionRegistry:
    def __init__(self, *, registry: ConnectorRegistry | None = None) -> None:
        self._registry = registry
        self._records: dict[tuple[str, str], ConnectorVersionRecord] = {}
        self._defaults: dict[str, str] = {}

    def register(self, record: ConnectorVersionRecord, *, make_default: bool = False, allow_replace: bool = False) -> None:
        record.validate()
        key = (str(record.connector_id).strip(), str(record.version).strip())
        if key in self._records and not allow_replace:
            raise KeyError(f'connector version already registered: {record.connector_id}:{record.version}')
        if record.replacement_version is not None and (str(record.connector_id).strip(), str(record.replacement_version).strip()) == key:
            raise ValueError('replacement_version must differ from version')
        if self._registry is not None:
            self._registry.list_entries(connector_id=record.connector_id, enabled_only=False)
        self._records[key] = record
        if make_default or str(record.connector_id).strip() not in self._defaults:
            self.set_default(connector_id=str(record.connector_id), version=str(record.version))

    def set_default(self, *, connector_id: str, version: str) -> None:
        connector = str(connector_id or '').strip()
        ver = str(version or '').strip()
        if not connector:
            raise ValueError('connector_id is required')
        if not ver:
            raise ValueError('version is required')
        record = self._records.get((connector, ver))
        if record is not None and record.deprecated:
            raise ValueError(f'cannot set deprecated connector version as default: {connector}:{ver}')
        if (connector, ver) not in self._records and self._registry is not None:
            entries = self._registry.list_entries(connector_id=connector, enabled_only=False)
            if not any(str(item.version) == ver for item in entries):
                raise KeyError(f'unknown connector version: {connector}:{ver}')
        self._defaults[connector] = ver

    def resolve(self, *, connector_id: str, requested_version: str | None = None, strict: bool = True) -> str:
        connector = str(connector_id or '').strip()
        if not connector:
            raise ValueError('connector_id is required')
        if requested_version is not None:
            version = str(requested_version).strip()
            record = self._records.get((connector, version))
            if record is None:
                if self._registry is not None:
                    entries = self._registry.list_entries(connector_id=connector, enabled_only=False)
                    if any(str(item.version) == version for item in entries):
                        return version
                raise KeyError(f'unknown connector version: {connector}:{requested_version}')
            if record.deprecated and record.replacement_version:
                if strict:
                    raise ValueError(f'deprecated connector version requested: {connector}:{version} -> {record.replacement_version}')
                return str(record.replacement_version)
            return str(record.version)
        version = self._defaults.get(connector)
        if version:
            return str(version)
        if self._registry is not None:
            entries = self._registry.list_entries(connector_id=connector, enabled_only=False)
            if entries:
                return str(entries[0].version)
        raise KeyError(f'no default connector version for {connector}')

    def list_versions(self, *, connector_id: str) -> tuple[ConnectorVersionRecord, ...]:
        connector = str(connector_id).strip()
        records = [item for item in self._records.values() if str(item.connector_id) == connector]
        return tuple(sorted(records, key=lambda item: str(item.version)))

    def snapshot(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                'connector_id': str(item.connector_id),
                'version': str(item.version),
                'status': str(item.status),
                'deprecated': bool(item.deprecated),
                'replacement_version': None if item.replacement_version is None else str(item.replacement_version),
                'is_default': self._defaults.get(str(item.connector_id)) == str(item.version),
                'metadata': dict(item.metadata),
            }
            for item in sorted(self._records.values(), key=lambda item: (str(item.connector_id), str(item.version)))
        )


__all__ = [
    'CANON_CONNECTOR_VERSION_REGISTRY',
    'ConnectorVersionRecord',
    'ConnectorVersionRegistry',
]
