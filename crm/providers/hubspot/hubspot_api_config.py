from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HubSpotApiConfig:
    base_url: str = 'https://api.hubapi.com'
    oauth_base_url: str = 'https://api.hubapi.com'
    timeout_seconds: float = 20.0
