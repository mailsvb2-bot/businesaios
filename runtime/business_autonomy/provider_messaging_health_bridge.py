from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding
from runtime.messaging_capability.channel_health import ChannelHealth


@dataclass(frozen=True)
class ProviderMessagingHealthSignal:
    channel: str
    measurable: bool
    healthy: bool
    health_score: float
    reason: str


def resolve_provider_messaging_health_signal(*, provider, probe_result) -> ProviderMessagingHealthSignal | None:
    binding = describe_provider_messaging_binding(provider)
    if binding is None or not bool(binding.live_probe_supported):
        return None

    status = str(getattr(probe_result, 'status', '') or '').strip()
    ok = bool(getattr(probe_result, 'ok', False))

    if status in {'probe_prepared_only', 'ready_for_credentials', 'ready_for_live_probe'}:
        return ProviderMessagingHealthSignal(
            channel=binding.channel,
            measurable=False,
            healthy=True,
            health_score=1.0,
            reason=status or 'neutral_probe_result',
        )

    if status == 'probe_live_ok' and ok:
        return ProviderMessagingHealthSignal(
            channel=binding.channel,
            measurable=True,
            healthy=True,
            health_score=1.0,
            reason='provider_live_probe_ok',
        )

    if status in {'probe_live_failed', 'probe_rejected_misconfigured', 'misconfigured', 'invalid_secret_shape', 'missing_required_secrets'}:
        return ProviderMessagingHealthSignal(
            channel=binding.channel,
            measurable=True,
            healthy=False,
            health_score=0.0,
            reason=status,
        )

    return ProviderMessagingHealthSignal(
        channel=binding.channel,
        measurable=False,
        healthy=True,
        health_score=1.0,
        reason=status or 'unknown_probe_result',
    )


def signal_to_metadata(signal: ProviderMessagingHealthSignal | None) -> dict[str, Any]:
    if signal is None:
        return {}
    return {
        'channel': signal.channel,
        'measurable': signal.measurable,
        'healthy': signal.healthy,
        'health_score': signal.health_score,
        'reason': signal.reason,
    }


def apply_provider_probe_result_to_registry(*, registry, provider, probe_result):
    signal = resolve_provider_messaging_health_signal(provider=provider, probe_result=probe_result)
    if signal is None or not signal.measurable:
        return signal
    registry.set(
        ChannelHealth(
            channel=signal.channel,
            healthy=signal.healthy,
            health_score=float(signal.health_score),
            reason=signal.reason,
        )
    )
    return signal
