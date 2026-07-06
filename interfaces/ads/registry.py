from __future__ import annotations

from collections.abc import Mapping
from typing import Generic, TypeVar

from interfaces.common.registry_capability_contract import build_registry_entry

from .base import AdsPlatform, AdsReadConnector

TConnector = TypeVar('TConnector', bound=AdsReadConnector)


CONNECTORS = {
    'google_ads': build_registry_entry(
        name='google_ads',
        status='implemented',
        read=True,
        write=False,
        verify=False,
        supports_dry_run=False,
        supports_idempotency=False,
        production_ready=False,
        action_types=(),
    ),
    'tiktok_ads': build_registry_entry(name='tiktok_ads', status='not_implemented'),
    'meta_ads': build_registry_entry(name='meta_ads', status='not_implemented'),
    'telegram_ads': build_registry_entry(name='telegram_ads', status='not_implemented'),
    'vk_ads': build_registry_entry(name='vk_ads', status='not_implemented'),
    'yandex_direct': build_registry_entry(name='yandex_direct', status='not_implemented'),
    'google_display': build_registry_entry(name='google_display', status='not_implemented'),
    'google_search': build_registry_entry(name='google_search', status='not_implemented'),
    'linkedin_ads': build_registry_entry(name='linkedin_ads', status='not_implemented'),
    'youtube_ads': build_registry_entry(name='youtube_ads', status='not_implemented'),
}


def normalize_ads_platform(platform: AdsPlatform | str) -> AdsPlatform:
    if isinstance(platform, AdsPlatform):
        return platform
    text = str(platform or '').strip()
    if not text:
        raise ValueError('platform is required')
    return AdsPlatform(text)


class AdsConnectorRegistry(Generic[TConnector]):
    def __init__(self) -> None:
        self._items: dict[AdsPlatform, TConnector] = {}

    def register(self, connector: TConnector, *, allow_replace: bool = False) -> None:
        platform = normalize_ads_platform(getattr(connector, 'platform', None))
        if platform in self._items and not allow_replace:
            raise KeyError(f'Ads connector already registered for platform={platform.value}')
        truth = CONNECTORS.get(platform.value)
        if truth is None:
            raise KeyError(f'unknown ads platform={platform.value}')
        if not truth['implemented']:
            raise ValueError(f'cannot register runtime connector for not_implemented platform={platform.value}')
        self._items[platform] = connector

    def get(self, platform: AdsPlatform | str) -> TConnector:
        normalized = normalize_ads_platform(platform)
        if normalized not in self._items:
            raise KeyError(f'Ads connector not registered for platform={normalized.value}')
        return self._items[normalized]

    def get_optional(self, platform: AdsPlatform | str) -> TConnector | None:
        return self._items.get(normalize_ads_platform(platform))

    def has(self, platform: AdsPlatform | str) -> bool:
        return normalize_ads_platform(platform) in self._items

    def snapshot(self) -> tuple[dict[str, object], ...]:
        rows = []
        for platform in sorted(self._items, key=lambda item: item.value):
            truth: Mapping[str, object] = CONNECTORS[platform.value]
            rows.append({
                'platform': platform.value,
                'registered': True,
                'implemented': bool(truth['implemented']),
                'production_ready': bool(truth['production_ready']),
                'write': bool(truth['write']),
                'verify': bool(truth['verify']),
            })
        return tuple(rows)


__all__ = ['AdsConnectorRegistry', 'CONNECTORS', 'normalize_ads_platform']
