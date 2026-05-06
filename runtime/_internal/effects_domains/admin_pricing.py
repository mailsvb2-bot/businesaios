"""Pricing governance I/O and validation. Executed ONLY via RuntimeExecutor."""

from __future__ import annotations

import json
from pathlib import Path

from runtime.platform.config.env_flags import env_bool, env_path
from runtime._internal.effects_domains.admin_pricing_support import persist_pricing_version_override


def validate_pricing_change(
    *,
    admin_id: str,
    requested_by: str | None,
    pricing_version: str,
) -> None:
    """Raise RuntimeError if validation fails."""
    rb = str(requested_by or "").strip()
    if rb and rb == str(admin_id):
        allow = env_bool("ALLOW_SELF_APPROVE", False)
        if not allow:
            raise RuntimeError("SELF_APPROVAL_FORBIDDEN")

    v = str(pricing_version or "").strip()
    if not v:
        raise RuntimeError("PRICING_VERSION_REQUIRED")

    prod_strict = env_bool("PRODUCTION_STRICT_MODE", False)
    if prod_strict:
        lv = v.lower().strip()
        if lv in {"v1", "1", "default"} or lv.startswith("v1."):
            raise RuntimeError("PRICING_VERSION_LOOKS_DEFAULT")


def execute_plan_price_update(
    *,
    plan_id: int,
    new_price: int,
    pricing_version: str,
    plans_path: Path | None = None,
    override_path: Path | None = None,
) -> dict:
    """Update data/plans.json and persist version override. Returns result dict."""
    pid = int(plan_id)
    price = int(new_price)
    v = str(pricing_version or "").strip()
    if not v:
        raise RuntimeError("PRICING_VERSION_REQUIRED")

    path = plans_path or env_path("PLANS_PATH", "data/plans.json")
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        raise RuntimeError(f"PLANS_NOT_FOUND:{path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"PLANS_READ_FAILED:{e}")

    if not isinstance(data, list):
        raise RuntimeError("PLANS_FORMAT_INVALID")

    updated = False
    for item in data:
        if not isinstance(item, dict):
            continue
        if int(item.get("plan_id") or -1) == pid:
            item["price"] = price
            updated = True
            break

    if not updated:
        raise RuntimeError(f"PLAN_ID_NOT_FOUND:{pid}")

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

    ov_path = override_path or env_path("PRICING_VERSION_OVERRIDE_PATH", "data/pricing_version_override.txt")
    override_persisted = False
    try:
        override_persisted = persist_pricing_version_override(override_path=ov_path, pricing_version=v)
    except Exception:
        override_persisted = False

    return {
        "plan_id": pid,
        "new_price": price,
        "pricing_version": v,
        "plans_path": str(path),
        "override_path": str(ov_path),
        "override_persisted": bool(override_persisted),
    }


__all__ = ["validate_pricing_change", "execute_plan_price_update"]
