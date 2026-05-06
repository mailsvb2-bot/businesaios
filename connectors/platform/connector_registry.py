from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from connectors.platform.connector_capability_contract import ConnectorCapabilityDescriptor
from connectors.platform.connector_contract import PlatformConnector


CANON_CONNECTOR_REGISTRY = True


@dataclass(frozen=True)
class ConnectorRegistryEntry:
    connector_id: str
    provider: str
    version: str
    connector: PlatformConnector
    rank: int = 100
    enabled: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        connector_id = str(self.connector_id or '').strip()
        provider = str(self.provider or '').strip()
        version = str(self.version or '').strip()
        if not connector_id:
            raise ValueError('connector_id is required')
        if not provider:
            raise ValueError('provider is required')
        if not version:
            raise ValueError('version is required')
        if int(self.rank) < 0:
            raise ValueError('rank must be >= 0')
        if not isinstance(self.connector, PlatformConnector):
            raise TypeError('connector must implement PlatformConnector')
        object.__setattr__(self, 'connector_id', connector_id)
        object.__setattr__(self, 'provider', provider)
        object.__setattr__(self, 'version', version)
        object.__setattr__(self, 'rank', int(self.rank))
        object.__setattr__(self, 'tags', tuple(sorted({str(item).strip() for item in self.tags if str(item).strip()})))

    @property
    def registry_key(self) -> tuple[str, str, str]:
        return (str(self.connector_id), str(self.provider), str(self.version))

    @property
    def capabilities(self) -> ConnectorCapabilityDescriptor:
        descriptor = self.connector.capabilities()
        if str(descriptor.connector_id) != str(self.connector_id):
            raise ValueError('connector capability descriptor connector_id mismatch')
        if str(descriptor.provider) != str(self.provider):
            raise ValueError('connector capability descriptor provider mismatch')
        if str(descriptor.version) != str(self.version):
            raise ValueError('connector capability descriptor version mismatch')
        return descriptor


class ConnectorRegistry:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], ConnectorRegistryEntry] = {}

    def register(self, entry: ConnectorRegistryEntry, *, allow_replace: bool = False) -> None:
        key = entry.registry_key
        if key in self._entries and not allow_replace:
            raise KeyError(
                f'connector already registered: connector_id={entry.connector_id} provider={entry.provider} version={entry.version}'
            )
        _ = entry.capabilities
        self._entries[key] = entry

    def register_many(self, entries: Iterable[ConnectorRegistryEntry], *, allow_replace: bool = False) -> None:
        pending = list(entries)
        validated: list[tuple[tuple[str, str, str], ConnectorRegistryEntry]] = []
        seen_in_batch: set[tuple[str, str, str]] = set()
        for entry in pending:
            key = entry.registry_key
            if key in seen_in_batch:
                raise KeyError(
                    f'duplicate connector registration in batch: connector_id={entry.connector_id} provider={entry.provider} version={entry.version}'
                )
            if key in self._entries and not allow_replace:
                raise KeyError(
                    f'connector already registered: connector_id={entry.connector_id} provider={entry.provider} version={entry.version}'
                )
            _ = entry.capabilities
            seen_in_batch.add(key)
            validated.append((key, entry))
        for key, entry in validated:
            self._entries[key] = entry

    def remove(self, *, connector_id: str, version: str, provider: str | None = None) -> None:
        cid = str(connector_id).strip()
        ver = str(version).strip()
        prov = None if provider is None else str(provider).strip()
        keys = [
            key
            for key in self._entries
            if key[0] == cid and key[2] == ver and (prov is None or key[1] == prov)
        ]
        for key in keys:
            self._entries.pop(key, None)

    def get(self, *, connector_id: str, version: str | None = None, provider: str | None = None) -> PlatformConnector:
        return self.get_entry(connector_id=connector_id, version=version, provider=provider).connector

    def get_entry(
        self,
        *,
        connector_id: str,
        version: str | None = None,
        provider: str | None = None,
        enabled_only: bool = False,
    ) -> ConnectorRegistryEntry:
        candidates = self.list_entries(
            connector_id=connector_id,
            provider=provider,
            enabled_only=enabled_only,
        )
        if version is not None:
            version_text = str(version).strip()
            version_matches = [entry for entry in candidates if str(entry.version) == version_text]
            if len(version_matches) == 1:
                return version_matches[0]
            if len(version_matches) > 1 and provider is None:
                providers = ', '.join(sorted({str(item.provider) for item in version_matches}))
                raise KeyError(
                    f'ambiguous connector version: connector_id={connector_id} version={version} providers=[{providers}]'
                )
            raise KeyError(f'unknown connector version: {connector_id}:{version}')
        if not candidates:
            raise KeyError(f'unknown connector: {connector_id}')
        if len(candidates) > 1 and provider is None:
            top_rank = int(candidates[0].rank)
            top = [item for item in candidates if int(item.rank) == top_rank]
            if len(top) > 1:
                providers = ', '.join(sorted({str(item.provider) for item in top}))
                raise KeyError(
                    f'ambiguous connector route: connector_id={connector_id} providers=[{providers}]'
                )
        return candidates[0]

    def list_entries(
        self,
        *,
        connector_id: str | None = None,
        provider: str | None = None,
        enabled_only: bool = True,
        operation: str | None = None,
        require_write: bool = False,
        require_verify: bool = False,
        required_tags: Iterable[str] | None = None,
    ) -> list[ConnectorRegistryEntry]:
        items = list(self._entries.values())
        if connector_id is not None:
            needle = str(connector_id).strip()
            items = [item for item in items if str(item.connector_id) == needle]
        if provider is not None:
            needle = str(provider).strip()
            items = [item for item in items if str(item.provider) == needle]
        if enabled_only:
            items = [item for item in items if item.enabled]
        if operation is not None:
            op = str(operation).strip()
            items = [item for item in items if item.capabilities.supports_operation(op)]
        if require_write:
            items = [item for item in items if item.capabilities.supports_write]
        if require_verify:
            items = [item for item in items if item.capabilities.supports_verify]
        if required_tags:
            tags = {str(item).strip() for item in required_tags if str(item).strip()}
            if tags:
                items = [item for item in items if tags.issubset(set(item.tags))]
        return sorted(
            items,
            key=lambda item: (
                0 if item.enabled else 1,
                int(item.rank),
                str(item.provider),
                str(item.connector_id),
                str(item.version),
            ),
        )

    def list_connectors(self) -> tuple[str, ...]:
        return tuple(sorted({str(item.connector_id) for item in self._entries.values()}))

    def providers_for(self, *, connector_id: str) -> tuple[str, ...]:
        providers = {
            str(item.provider)
            for item in self._entries.values()
            if str(item.connector_id) == str(connector_id).strip()
        }
        return tuple(sorted(providers))

    def snapshot(self) -> tuple[dict[str, object], ...]:
        rows: list[dict[str, object]] = []
        for entry in self.list_entries(enabled_only=False):
            rows.append(
                {
                    'connector_id': str(entry.connector_id),
                    'provider': str(entry.provider),
                    'version': str(entry.version),
                    'rank': int(entry.rank),
                    'enabled': bool(entry.enabled),
                    'tags': list(entry.tags),
                    'capabilities': entry.capabilities.as_dict(),
                }
            )
        return tuple(rows)


__all__ = [
    'CANON_CONNECTOR_REGISTRY',
    'ConnectorRegistry',
    'ConnectorRegistryEntry',
]
