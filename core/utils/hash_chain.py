"""Hash chain for ledger integrity."""
from __future__ import annotations

import hashlib
from typing import Any

from core.utils.canonical import canonical_json_bytes

GENESIS = "GENESIS"


def entry_hash(*, prev_hash: str, fields: dict[str, Any]) -> str:
    prev = (prev_hash or GENESIS).encode("utf-8")
    body = canonical_json_bytes(fields)
    return hashlib.sha256(prev + b"|" + body).hexdigest()


__all__ = ["GENESIS", "entry_hash"]
