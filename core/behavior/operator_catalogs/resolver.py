from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from core.tenancy.normalization import normalize_tenant_id


def _deep_get(d: Mapping[str, Any] | None, path: str) -> Any:
    cur: Any = d
    for part in path.split('.'):
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(part)
    return cur


def resolve_operator_catalog_id(*, product: Mapping[str, Any] | None, tenant_id: str | None = None) -> str:
    """Resolve operator_catalog_id from product contract dict.

    This is intentionally flexible, because different deployments may
    place module configs differently.

    Priority (first match wins):
      1) modules.behavior_os.operator_catalog_ref / _id
      2) modules.behavior_dirac.operator_catalog_ref / _id
      3) behavior.operator_catalog_ref / _id
      4) default
    """

    p = dict(product or {})
    for key in (
        "modules.behavior_os.operator_catalog_ref",
        "modules.behavior_os.operator_catalog_id",
        "modules.behavior_dirac.operator_catalog_ref",
        "modules.behavior_dirac.operator_catalog_id",
        "behavior.operator_catalog_ref",
        "behavior.operator_catalog_id",
    ):
        v = _deep_get(p, key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "default"


def resolve_operator_context(*, product: Mapping[str, Any] | None, tenant_id: str | None = None) -> dict[str, Any]:
    """Resolve operator context from product dict.

    Returns a dict that can be fed into DiracBehaviorModel.evolve(...) context.
    """
    p = dict(product or {})
    modules = p.get("modules") if isinstance(p.get("modules"), Mapping) else {}

    # Optional overrides live next to the catalog ref.
    overrides: dict[str, Any] = {}
    for mod_key in ("behavior_os", "behavior_dirac"):
        mv = modules.get(mod_key)
        if isinstance(mv, Mapping):
            ov = mv.get("operator_overrides")
            if isinstance(ov, Mapping):
                overrides = dict(ov)
                break

    # Optional operator policy catalog ref (safety rails).
    policy_ref = None
    for key in (
        "modules.behavior_os.operator_policy_catalog_ref",
        "modules.behavior_os.operator_policy_catalog_id",
        "modules.behavior_dirac.operator_policy_catalog_ref",
        "modules.behavior_dirac.operator_policy_catalog_id",
        "behavior.operator_policy_catalog_ref",
        "behavior.operator_policy_catalog_id",
    ):
        v = _deep_get(p, key)
        if isinstance(v, str) and v.strip():
            policy_ref = v.strip()
            break

    return {
        "operator_catalog_id": resolve_operator_catalog_id(product=p, tenant_id=tenant_id),
        "operator_overrides": overrides,
        "operator_policy_catalog_ref": policy_ref,
        "domain": str(p.get("domain") or "").strip(),
        # Identity hints for resolvers (may be empty if caller does not have it).
        "tenant_id": normalize_tenant_id(tenant_id),
        "product_id": str(p.get("product_id") or p.get("id") or ""),
    }
