"""Autopilot contract resolver.

Source of truth:
- product.autopilot_contract_ref (preferred)
- env AUTOPILOT_CONTRACT_REF (fallback)
- config/autopilot/default.yaml
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.autopilot.loader import load_autopilot_contract_from_env


def resolve_autopilot_contract(*, product: Mapping[str, Any] | None, tenant_id: str) -> Any:
    ref = ""
    try:
        p = dict(product or {})
        ref = str(p.get("autopilot_contract_ref") or "").strip()
    except Exception:
        ref = ""
    resolved_tenant_id = str(tenant_id or "").strip()
    return load_autopilot_contract_from_env(tenant_id=resolved_tenant_id, ref=ref)
