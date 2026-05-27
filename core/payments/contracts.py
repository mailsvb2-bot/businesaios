from __future__ import annotations

import re

# Canonical contract for payment_created.payload.external_id
#
# - MUST be present and non-empty.
# - MUST be stable and unique per external payment in provider.
# - MUST be safe to log and use as a primary key.
#
# YooKassa IDs are typically URL-safe strings; we accept a conservative subset.
_EXTERNAL_ID_RE = re.compile(r"^[A-Za-z0-9_\-:.]{6,200}$")


def validate_payment_external_id(external_id: str) -> str:
    ext = str(external_id or "").strip()
    if not ext:
        raise ValueError("payment_created.external_id is required")
    if not _EXTERNAL_ID_RE.match(ext):
        raise ValueError("payment_created.external_id has invalid format")
    return ext
