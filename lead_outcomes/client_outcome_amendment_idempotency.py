from __future__ import annotations

import hashlib


CANON_CLIENT_OUTCOME_AMENDMENT_IDEMPOTENCY = True


def amendment_fingerprint(*, order_id: str, package_id: str, requested_clients: int) -> str:
    raw = f"{str(order_id).strip()}::{str(package_id).strip()}::{int(requested_clients)}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()
