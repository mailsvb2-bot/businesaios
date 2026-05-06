from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True

from datetime import datetime, timezone
from typing import Any, Optional


def safe_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def resolve_tenant_id(*, state: Any, product: dict[str, Any]) -> Optional[str]:
    raw = getattr(state, "tenant_id", None) or product.get("tenant_id")
    tenant_id = str(raw or "").strip()
    if not tenant_id:
        return None
    if tenant_id.lower() in {"default", "legacy"}:
        return None
    return tenant_id


def resolve_product_id(*, product: dict[str, Any]) -> Optional[str]:
    product_id = product.get("product_id") or product.get("id") or product.get("sku")
    product_id = str(product_id).strip() if product_id is not None else ""
    return product_id or None


def resolve_float(*values: Any) -> Optional[float]:
    for value in values:
        try:
            if value is None:
                continue
            return float(value)
        except Exception:
            continue
    return None


def timestamp_to_utc_datetime(timestamp_ms: int) -> Optional[datetime]:
    if timestamp_ms <= 0:
        return None
    try:
        return datetime.fromtimestamp(float(timestamp_ms) / 1000.0, tz=timezone.utc)
    except Exception:
        return None
