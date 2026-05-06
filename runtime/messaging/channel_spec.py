from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelSpec:
    key: str
    family: str
    provider_env_prefix: str
    mode_default: str
    transport_kind: str
