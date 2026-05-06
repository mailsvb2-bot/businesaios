from __future__ import annotations

from typing import Mapping

_ALLOWED_PROVIDER_METADATA: dict[str, tuple[str, ...]] = {
    "hubspot": ("portal_id", "hub_id", "account_id", "region"),
    "pipedrive": ("company_domain", "account_id", "region"),
}


def extract_provider_connection_metadata(*, provider_key: str, metadata: Mapping[str, object]) -> dict[str, object]:
    allowed = _ALLOWED_PROVIDER_METADATA.get(provider_key, ())
    sanitized: dict[str, object] = {}
    for key in allowed:
        value = metadata.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                sanitized[key] = stripped
        elif value is not None:
            sanitized[key] = value
    return sanitized
