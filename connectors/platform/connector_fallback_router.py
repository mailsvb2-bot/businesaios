from __future__ import annotations

from dataclasses import dataclass, field

from connectors.platform.connector_health_monitor import ConnectorHealthMonitor
from connectors.platform.connector_registry import ConnectorRegistry, ConnectorRegistryEntry
from connectors.platform.connector_version_registry import ConnectorVersionRegistry


CANON_CONNECTOR_FALLBACK_ROUTER = True


def plan_connector_candidates(
    *,
    registry: ConnectorRegistry,
    version_registry: ConnectorVersionRegistry | None,
    connector_id: str,
    operation: str,
    requested_version: str | None = None,
    preferred_provider: str | None = None,
    require_write: bool = False,
    require_verify: bool = False,
    allow_replacement_version_failover: bool = False,
) -> list[ConnectorRegistryEntry]:
    resolved_version = requested_version
    if resolved_version is None and version_registry is not None:
        resolved_version = version_registry.resolve(connector_id=connector_id, requested_version=None, strict=False)
    candidates = registry.list_entries(
        connector_id=connector_id,
        enabled_only=True,
        operation=operation,
        require_write=require_write,
        require_verify=require_verify,
    )
    normalized_version = None if resolved_version is None else str(resolved_version).strip()
    normalized_provider = None if preferred_provider is None else str(preferred_provider).strip()
    same_version: list[ConnectorRegistryEntry] = []
    replacement_version: list[ConnectorRegistryEntry] = []
    for entry in candidates:
        entry_version = str(entry.version)
        if normalized_version is None or entry_version == normalized_version:
            same_version.append(entry)
            continue
        if not allow_replacement_version_failover or version_registry is None or normalized_version is None:
            continue
        for record in version_registry.list_versions(connector_id=connector_id):
            if str(record.version) == normalized_version and str(record.replacement_version or '') == entry_version:
                replacement_version.append(entry)
                break

    def _sort_key(entry: ConnectorRegistryEntry) -> tuple[int, int, str, str]:
        provider_penalty = 0 if normalized_provider and str(entry.provider) == normalized_provider else 1
        return (provider_penalty, int(entry.rank), str(entry.provider), str(entry.version))

    return sorted(same_version, key=_sort_key) + sorted(replacement_version, key=_sort_key)


@dataclass(frozen=True)
class FallbackRoute:
    connector_id: str
    version: str
    provider: str
    reason: str
    fallback_depth: int
    attempted_versions: tuple[str, ...] = field(default_factory=tuple)


class ConnectorFallbackRouter:
    """Infra-only fallback selector.

    This router must never invent new actions or change business intent.
    It only selects a healthy connector implementation for the same declared
    connector_id + operation surface.
    """

    def __init__(
        self,
        *,
        registry: ConnectorRegistry,
        version_registry: ConnectorVersionRegistry | None = None,
        health_monitor: ConnectorHealthMonitor | None = None,
    ) -> None:
        self._registry = registry
        self._version_registry = version_registry
        self._health_monitor = health_monitor

    def resolve(
        self,
        *,
        connector_id: str,
        operation: str,
        requested_version: str | None = None,
        preferred_provider: str | None = None,
        require_write: bool = False,
        require_verify: bool = False,
    ) -> FallbackRoute:
        attempted: list[str] = []
        candidates = plan_connector_candidates(
            registry=self._registry,
            version_registry=self._version_registry,
            connector_id=connector_id,
            operation=operation,
            requested_version=requested_version,
            preferred_provider=preferred_provider,
            require_write=require_write,
            require_verify=require_verify,
            allow_replacement_version_failover=False,
        )
        if not candidates:
            raise RuntimeError(
                f'no connector candidates for connector_id={connector_id} operation={operation} version={requested_version} provider={preferred_provider}'
            )

        for depth, candidate in enumerate(candidates):
            attempted.append(f'{candidate.provider}:{candidate.version}')
            if not self._entry_matches(candidate, operation=operation, require_write=require_write, require_verify=require_verify):
                continue
            if not self._is_healthy(candidate):
                continue
            return FallbackRoute(
                connector_id=str(candidate.connector_id),
                version=str(candidate.version),
                provider=str(candidate.provider),
                reason='primary' if depth == 0 else 'fallback_healthy_alternative',
                fallback_depth=depth,
                attempted_versions=tuple(attempted),
            )
        raise RuntimeError(
            f'no healthy connector route for connector_id={connector_id} operation={operation} attempted={attempted}'
        )

    def _entry_matches(
        self,
        entry: ConnectorRegistryEntry,
        *,
        operation: str,
        require_write: bool,
        require_verify: bool,
    ) -> bool:
        descriptor = entry.capabilities
        if not descriptor.supports_operation(operation):
            return False
        if require_write and not descriptor.supports_write:
            return False
        if require_verify and not descriptor.supports_verify:
            return False
        return True

    def _is_healthy(self, entry: ConnectorRegistryEntry) -> bool:
        if self._health_monitor is None:
            return True
        return self._health_monitor.is_healthy(
            connector_id=entry.connector_id,
            version=entry.version,
            provider=entry.provider,
        )


__all__ = [
    'CANON_CONNECTOR_FALLBACK_ROUTER',
    'ConnectorFallbackRouter',
    'FallbackRoute',
    'plan_connector_candidates',
]
