from __future__ import annotations

from typing import Any

from application.business_autonomy.provider_messaging_binding import ProviderMessagingBinding

CANON_PROVIDER_MESSAGING_METADATA = True


def messaging_binding_to_metadata(binding: ProviderMessagingBinding | None) -> dict[str, Any]:
    if binding is None:
        return {}
    return {
        "channel": str(binding.channel),
        "required_capabilities": dict(binding.required_capabilities),
        "live_probe_supported": bool(binding.live_probe_supported),
    }


__all__ = ["CANON_PROVIDER_MESSAGING_METADATA", "messaging_binding_to_metadata"]
