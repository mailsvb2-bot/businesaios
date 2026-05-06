from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.tenancy.normalization import normalize_tenant_id

from .loader import load_operator_policy_catalog
from .model import OperatorPolicyCatalog


@dataclass(frozen=True)
class OperatorPolicyCatalogResolver:
    """Resolve policy catalogs with a deterministic fallback chain.

    Resolution is file-based (YAML) to keep policy changes config-only.
    """

    root_dir: str = "products/operator_policy_catalogs"

    def resolve(
        self,
        *,
        catalog_ref: str | None,
        tenant_id: str | None,
        product_id: str | None,
        env: str | None = None,
    ) -> OperatorPolicyCatalog:
        if catalog_ref:
            path = self._path_for_ref(catalog_ref)
            return load_operator_policy_catalog(path, name=catalog_ref)

        env = env or "prod"
        product = str(product_id or "").strip()
        tenant = normalize_tenant_id(tenant_id)
        candidates: list[str] = []
        if tenant and product:
            candidates.append(f"{tenant}:{product}:{env}")
        if product:
            candidates.append(f"default:{product}:{env}")
            candidates.append(f"default:{product}")
        candidates.append("default")

        for ref in candidates:
            path = self._path_for_ref(ref)
            if path.exists():
                return load_operator_policy_catalog(path, name=ref)

        raise FileNotFoundError("No operator policy catalog found; expected default.yaml to exist")

    def _path_for_ref(self, ref: str) -> Path:
        safe = ref.replace(":", "_")
        return Path(self.root_dir) / f"{safe}.yaml"
