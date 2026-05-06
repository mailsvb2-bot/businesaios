from __future__ import annotations

import time
import uuid


def _clean(value: str, *, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def new_snapshot_id(*, tenant_id: str, business_id: str) -> str:
    tenant = _clean(tenant_id, default="tenant")
    business = _clean(business_id, default="business")
    return f"wsnap_{tenant}_{business}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:10]}"


def build_snapshot_key(*, tenant_id: str, business_id: str) -> str:
    tenant = _clean(tenant_id, default="tenant")
    business = _clean(business_id, default="business")
    return f"{tenant}:{business}"


def new_event_id(prefix: str = "wmevt") -> str:
    p = _clean(prefix, default="wmevt")
    return f"{p}_{uuid.uuid4().hex}"
