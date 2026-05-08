from __future__ import annotations

from dataclasses import dataclass, field

from runtime.business_autonomy.provider_transport_bindings import provider_endpoint_url


@dataclass(frozen=True)
class HubSpotApiConfig:
    base_url: str = field(default_factory=lambda: provider_endpoint_url('hubspot'))
    oauth_base_url: str = field(default_factory=lambda: provider_endpoint_url('hubspot', 'oauth_base_url'))
    timeout_seconds: float = 20.0
