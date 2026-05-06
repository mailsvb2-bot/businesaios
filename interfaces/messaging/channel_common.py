from __future__ import annotations

"""Canonical thin factory helpers for channel-facing interfaces.

Business logic must stay in messaging_runtime and shared provider primitives.
Channel packages should keep only channel identity/config and use these helpers
for runner/adapter/binding construction.
"""

from interfaces.messaging._shared.provider_surface import make_adapter_type, make_runner_type
from interfaces.messaging_runtime.channel_factory import build_channel_binding


def make_channel_runner(*, provider: str, env_prefix: str, default_mode: str):
    return make_runner_type(provider=provider, env_prefix=env_prefix, default_mode=default_mode)


def make_channel_adapter(*, runner_factory):
    return make_adapter_type(runner_factory=runner_factory)


def build_channel_binding_for(*, channel: str, sender=None):
    return build_channel_binding(channel=channel, sender=sender)


__all__ = [
    "make_channel_runner",
    "make_channel_adapter",
    "build_channel_binding_for",
]
