"""Idempotency key derivation helpers.

This module is a tiny primitive: given a JSON-like payload, derive a stable
hash key. It is useful for *internal* idempotency when the caller wants a
deterministic key rather than a random UUID.

Canonical external API still lives under core.api.idempotency_keygen.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def make_idempotency_key(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
