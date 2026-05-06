from __future__ import annotations

from dataclasses import dataclass

from core.behavior.operator_catalogs.default_registry import default_operator_catalog_registry
from core.behavior.operator_catalogs.models import OperatorCatalog
from core.behavior.operator_catalogs.registry import OperatorCatalogRegistry
from core.tenancy.normalization import normalize_tenant_id


@dataclass(frozen=True)
class OperatorCatalogKey:
    tenant_id: str
    product_id: str
    domain: str = ""
    environment: str = "prod"


class OperatorCatalogResolver:
    """Canonical resolver: tenant + product + env -> OperatorCatalog.

    The catalog alphabet remains fixed in code; catalogs only tune coefficients.
    """

    def __init__(self, *, catalogs: OperatorCatalogRegistry | None = None) -> None:
        self._catalogs = catalogs or default_operator_catalog_registry()

    def resolve(self, *, key: OperatorCatalogKey, fallback_catalog_id: str = "default") -> OperatorCatalog:
        tenant = normalize_tenant_id(key.tenant_id)
        product = str(key.product_id or "").strip()
        env = str(key.environment or "prod").strip() or "prod"
        dom = str(key.domain or "").strip()
        fallback_ref = str(fallback_catalog_id or "default").strip() or "default"

        if not product:
            c = self._catalogs.get(fallback_ref)
            if c:
                return c
            raise KeyError(f"Operator catalog not found: {fallback_ref}")

        candidates: list[str] = []
        if tenant:
            candidates.extend([
                f"{tenant}:{product}:{env}",
                f"{tenant}:{product}:prod",
            ])
        candidates.extend([
            f"default:{product}:{env}",
            f"default:{product}:prod",
        ])
        if dom:
            if tenant:
                candidates.append(f"{tenant}:{dom}:{env}")
            candidates.append(f"default:{dom}:{env}")
        candidates.append(fallback_ref)

        for cid in [c for c in candidates if c]:
            cat = self._catalogs.get(cid)
            if cat is not None:
                return cat
        raise KeyError(f"Operator catalog not found. Tried: {candidates}")
