"""Platform-layer hash-chain.

This is the storage-side integrity chain for the execution ledger.

It mirrors the hash-chain algorithm used by the system but lives in
platform_layer to keep the adapter layer independent from the core package.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict

from runtime.platform.utils.canonical import canonical_json_bytes

GENESIS = "GENESIS"


def entry_hash(*, prev_hash: str, fields: dict[str, Any]) -> str:
    prev = (prev_hash or GENESIS).encode("utf-8")
    body = canonical_json_bytes(fields)
    return hashlib.sha256(prev + b"|" + body).hexdigest()
