from __future__ import annotations

import hashlib


def build_state_id(*, generated_at_ms: int, salt: str) -> str:
    raw = f"{generated_at_ms}:{salt}".encode()
    return hashlib.sha256(raw).hexdigest()[:20]
