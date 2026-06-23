from __future__ import annotations

from datetime import datetime, timezone

CANON_TENANT_TIME = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = ["CANON_TENANT_TIME", "utc_now"]
