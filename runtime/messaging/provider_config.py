"""Canonical immutable provider-transport configuration contract."""

from __future__ import annotations

from dataclasses import dataclass

CANON_PROVIDER_TRANSPORT_CONFIG = True


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    env_prefix: str
    mode: str
    endpoint: str
    sender: str
    token_present: bool


__all__ = ["CANON_PROVIDER_TRANSPORT_CONFIG", "ProviderConfig"]
