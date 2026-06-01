from __future__ import annotations

"""Helpers for read-only demo connectors that are intentionally not live integrations."""

from typing import Any, Dict, Mapping

DEMO_CONNECTOR_REASON = 'connector_not_bundled'


def build_demo_connector_metadata(*, platform: str) -> dict[str, Any]:
    return {
        'connector_mode': 'stub',
        'production_ready': False,
        'platform': str(platform),
        'reason': DEMO_CONNECTOR_REASON,
        'write_enabled': False,
        'verify_enabled': False,
    }


def build_demo_write_error(*, platform: str) -> dict[str, Any]:
    meta = build_demo_connector_metadata(platform=platform)
    return {
        'ok': False,
        'error': 'write_not_supported',
        'actionable': False,
        **meta,
    }


def ensure_demo_registry_truth(*, platform: str, entry: Mapping[str, Any]) -> None:
    if bool(entry.get('production_ready', False)):
        raise ValueError(f'demo platform cannot be production_ready: {platform}')
    if bool(entry.get('write', False)):
        raise ValueError(f'demo platform cannot advertise write support: {platform}')
    if bool(entry.get('verify', False)):
        raise ValueError(f'demo platform cannot advertise verify support: {platform}')


def assert_live_write_allowed(*, platform: str, metadata: Mapping[str, Any] | None = None) -> None:
    meta = dict(metadata or {})
    if bool(meta.get('connector_mode') == 'stub') or bool(meta.get('production_ready') is False):
        raise RuntimeError(f'live writes are forbidden for non-live ads connector: {platform}')


__all__ = [
    'DEMO_CONNECTOR_REASON',
    'assert_live_write_allowed',
    'build_demo_connector_metadata',
    'build_demo_write_error',
    'ensure_demo_registry_truth',
]
