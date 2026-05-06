from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    env_prefix: str
    mode: str
    endpoint: str
    sender: str
    token_present: bool
