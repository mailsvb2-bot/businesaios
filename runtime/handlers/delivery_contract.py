"""Forward signed delivery metadata without choosing a messaging strategy.

Channel selection and fallback ranking remain owned by the canonical messaging
policy/effect path. Runtime handlers only preserve the action payload fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.messaging.channel_normalizer import normalize_channel

CANON_DELIVERY_METADATA_FORWARDER = True


def delivery_kwargs(
    payload: Mapping[str, Any] | None,
    *,
    default_channel: str = "telegram",
) -> dict[str, Any]:
    body = payload if isinstance(payload, Mapping) else {}
    policy = body.get("channel_policy")
    return {
        "channel": normalize_channel(
            str(body.get("channel") or default_channel)
        ),
        "channel_policy": dict(policy) if isinstance(policy, Mapping) else None,
    }


__all__ = ["CANON_DELIVERY_METADATA_FORWARDER", "delivery_kwargs"]
