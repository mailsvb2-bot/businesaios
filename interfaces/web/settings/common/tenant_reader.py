from __future__ import annotations


def read_tenant_id(value) -> str:
    text = str(value or "").strip()
    return text or "default"
