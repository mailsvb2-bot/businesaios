from __future__ import annotations

from typing import Any, Callable, Dict


def resolve_runtime_oauth_value(*, explicit: str | None, resolver: Callable[[], str], default: str = "") -> str:
    value = str(explicit or "").strip()
    if value:
        return value
    resolved = str(resolver() or "").strip()
    return resolved or default


def resolve_pending_account_id(*, tenant_id: str, raw: Dict[str, Any], extractor: Callable[[str, Dict[str, Any]], str]) -> str:
    return str(extractor(str(tenant_id), dict(raw or {})) or "")
