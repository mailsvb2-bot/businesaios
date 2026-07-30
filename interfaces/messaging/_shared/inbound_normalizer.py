from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.messaging.provider_inbound_decoder import decode_provider_inbound


def normalize_provider_inbound(
    *,
    provider_channel: str,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return decode_provider_inbound(
        channel=provider_channel,
        payload=payload,
    )


__all__ = ["normalize_provider_inbound"]
