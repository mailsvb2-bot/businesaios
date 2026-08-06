"""Stable transport-event identity shared by every messaging ingress surface."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

CANON_MESSAGING_EVENT_IDENTITY = True


def stable_transport_message_id(*, channel: str, payload: Mapping[str, Any]) -> str:
    """Return a deterministic ID when a provider omits its own event/message ID.

    Provider-supplied IDs remain authoritative. The synthetic ID is based only on
    canonical channel identity and the original JSON payload, so retries produce
    the same dedupe key while different payloads remain distinct.
    """

    canonical_payload = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(
        f"{str(channel).strip().lower()}\n{canonical_payload}".encode()
    ).hexdigest()
    return f"synthetic-{str(channel).strip().lower()}-{digest[:32]}"


__all__ = ["CANON_MESSAGING_EVENT_IDENTITY", "stable_transport_message_id"]
