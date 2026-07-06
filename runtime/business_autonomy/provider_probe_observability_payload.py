from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _signal_dict(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict((metadata or {}).get("messaging_health_signal") or {})
    return {str(k): raw[k] for k in raw}


def build_live_probe_labels(*, provider_key: str, status: str, mode: str, metadata: Mapping[str, Any] | None) -> dict[str, str]:
    signal = _signal_dict(metadata)
    labels = {
        'provider_key': str(provider_key),
        'status': str(status),
        'mode': str(mode),
    }
    if signal:
        channel = str(signal.get('channel') or '').strip()
        reason = str(signal.get('reason') or '').strip()
        measurable = str(bool(signal.get('measurable', False))).lower()
        healthy = str(bool(signal.get('healthy', False))).lower()
        if channel:
            labels['messaging_channel'] = channel
        if reason:
            labels['messaging_reason'] = reason
        labels['messaging_measurable'] = measurable
        labels['messaging_healthy'] = healthy
    return labels


def build_live_probe_gauge_payload(*, metadata: Mapping[str, Any] | None) -> tuple[str, float] | None:
    signal = _signal_dict(metadata)
    if not signal:
        return None
    if not bool(signal.get('measurable', False)):
        return None
    return 'provider_runtime.messaging_health_score', float(signal.get('health_score') or 0.0)


__all__ = [
    'build_live_probe_labels',
    'build_live_probe_gauge_payload',
]
