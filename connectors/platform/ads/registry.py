from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping

from interfaces.ads.base import AdsConnector, AdsPlatform
from interfaces.ads.capabilities import AdsCapabilities
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.ads.registry import CONNECTORS as ADS_INTERFACE_CONNECTORS


CANON_ADS_PLATFORM_REGISTRY = True


def _normalize_platform(platform: AdsPlatform | str) -> str:
    if isinstance(platform, AdsPlatform):
        return platform.value
    text = str(platform or '').strip()
    if not text:
        raise ValueError('platform is required')
    try:
        return AdsPlatform(text).value
    except Exception:
        return text


@dataclass(frozen=True)
class AdsConnectorBinding:
    platform: str
    connector: AdsConnector
    provider: str
    production_ready: bool

    def __post_init__(self) -> None:
        platform = _normalize_platform(self.platform)
        provider = str(self.provider or '').strip() or platform
        object.__setattr__(self, 'platform', platform)
        object.__setattr__(self, 'provider', provider)
        runtime_platform = _normalize_platform(getattr(self.connector, 'platform', platform))
        if runtime_platform != platform:
            raise ValueError('binding platform must match connector.platform')

    @property
    def capabilities(self) -> AdsCapabilities:
        caps = getattr(self.connector, 'capabilities', None)
        if caps is not None:
            resolved = caps()
            if isinstance(resolved, AdsCapabilities):
                return resolved
            if isinstance(resolved, ConnectorCapabilities):
                return AdsCapabilities(
                    read_inventory=bool(resolved.read),
                    read_metrics=bool(resolved.read),
                    write_campaigns=bool(resolved.write),
                    verify_writes=bool(resolved.verify),
                    dry_run=bool(resolved.dry_run),
                    idempotent=bool(resolved.idempotent),
                    requires_human_approval=bool(resolved.requires_human_approval),
                    metadata=dict(resolved.metadata or {}),
                )
        legacy = getattr(self.connector, 'connector_capabilities', None)
        if legacy is None:
            raise TypeError('ads connector must expose capabilities() or connector_capabilities()')
        resolved = legacy()
        if not isinstance(resolved, ConnectorCapabilities):
            raise TypeError('ads connector connector_capabilities() must return ConnectorCapabilities')
        return AdsCapabilities(
            read_inventory=bool(resolved.read),
            read_metrics=bool(resolved.read),
            write_campaigns=bool(resolved.write),
            verify_writes=bool(resolved.verify),
            dry_run=bool(resolved.dry_run),
            idempotent=bool(resolved.idempotent),
            requires_human_approval=bool(resolved.requires_human_approval),
            metadata=dict(resolved.metadata or {}),
        )


class AdsConnectorRegistry:
    def __init__(self) -> None:
        self._m: Dict[str, AdsConnectorBinding] = {}

    def register(self, connector: AdsConnector, *, allow_replace: bool = False, provider: str | None = None) -> None:
        platform = _normalize_platform(getattr(connector, 'platform', None))
        truth = ADS_INTERFACE_CONNECTORS.get(platform)
        if truth is None:
            raise KeyError(f'unknown ads platform in honest registry: {platform}')
        binding = AdsConnectorBinding(
            platform=platform,
            connector=connector,
            provider=str(provider or platform).strip() or platform,
            production_ready=bool(truth.get('production_ready', False)),
        )
        if platform in self._m and not allow_replace:
            raise KeyError(f'ads connector already registered for platform={platform}')
        self._m[platform] = binding

    def register_many(self, connectors: Iterable[AdsConnector], *, allow_replace: bool = False) -> None:
        pending = list(connectors)
        normalized: list[tuple[str, AdsConnectorBinding]] = []
        seen: set[str] = set()
        for connector in pending:
            platform = _normalize_platform(getattr(connector, 'platform', None))
            if platform in seen:
                raise KeyError(f'duplicate ads connector in batch for platform={platform}')
            truth = ADS_INTERFACE_CONNECTORS.get(platform)
            if truth is None:
                raise KeyError(f'unknown ads platform in honest registry: {platform}')
            if platform in self._m and not allow_replace:
                raise KeyError(f'ads connector already registered for platform={platform}')
            seen.add(platform)
            normalized.append((platform, AdsConnectorBinding(platform=platform, connector=connector, provider=platform, production_ready=bool(truth.get('production_ready', False)))))
        for platform, binding in normalized:
            self._m[platform] = binding

    def get(self, platform: AdsPlatform | str) -> AdsConnector:
        return self.get_binding(platform).connector

    def get_binding(self, platform: AdsPlatform | str) -> AdsConnectorBinding:
        key = _normalize_platform(platform)
        if key not in self._m:
            raise KeyError(f'No connector for platform={key}')
        return self._m[key]

    def has(self, platform: AdsPlatform | str) -> bool:
        return _normalize_platform(platform) in self._m

    def remove(self, platform: AdsPlatform | str) -> None:
        self._m.pop(_normalize_platform(platform), None)

    def snapshot(self) -> tuple[dict[str, object], ...]:
        rows = []
        for platform in sorted(self._m):
            binding = self._m[platform]
            rows.append({
                'platform': platform,
                'provider': binding.provider,
                'production_ready': binding.production_ready,
                'capabilities': binding.capabilities.as_dict(),
            })
        return tuple(rows)

    def platform_truth(self) -> Mapping[str, Mapping[str, object]]:
        return ADS_INTERFACE_CONNECTORS


__all__ = [
    'AdsConnectorBinding',
    'AdsConnectorRegistry',
    'CANON_ADS_PLATFORM_REGISTRY',
]
