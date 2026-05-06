from __future__ import annotations

"""Shared factories for provider-specific adapter/runner surfaces.

The per-provider modules remain import-stable, but the implementation shape now
lives in one place instead of being duplicated across each provider namespace.
"""

from interfaces.messaging._shared.provider_runtime import ProviderAdapter, ProviderRunner, build_config_for


def make_adapter_type(*, runner_factory):
    class Adapter(ProviderAdapter):
        def __init__(self):
            super().__init__(runner_factory=runner_factory)

    return Adapter


def make_runner_type(*, provider: str, env_prefix: str, default_mode: str):
    class Runner(ProviderRunner):
        def __init__(self):
            super().__init__(provider=provider, env_prefix=env_prefix, default_mode=default_mode)

    return Runner


def make_build_config(*, provider: str, env_prefix: str, default_mode: str):
    def build_config():
        return build_config_for(provider=provider, env_prefix=env_prefix, default_mode=default_mode)

    return build_config
