from __future__ import annotations

from interfaces.messaging._shared.mode_reader import env_str, read_mode, token_present
from interfaces.messaging._shared.provider_config import ProviderConfig


def build_provider_config(*, provider: str, env_prefix: str, default_mode: str) -> ProviderConfig:
    return ProviderConfig(
        provider=str(provider),
        env_prefix=str(env_prefix),
        mode=read_mode(env_prefix, default=default_mode),
        endpoint=env_str(f"{env_prefix}_ENDPOINT"),
        sender=env_str(f"{env_prefix}_SENDER"),
        token_present=token_present(env_prefix),
    )
