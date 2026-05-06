from __future__ import annotations


def filter_channels_by_health(*, ordered_channels: tuple[str, ...], registry) -> tuple[str, ...]:
    out = []
    for channel in tuple(ordered_channels or ()):
        health = registry.get(channel)
        if bool(health.healthy) and float(health.health_score) > 0.0:
            out.append(channel)
    return tuple(out)
