from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from config.env_flags import env_path
from core.offers.catalog_identity import LEGACY_OFFER_CATALOG_ID, normalize_catalog_id, product_catalog_candidates
from core.offers.catalog_registry import OfferCatalogRegistry, default_offer_catalog_registry
from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1
from core.offers.catalogs.yaml_catalog_loader import load_yaml_offer_catalog_spec
from core.offers.offer_types import OfferCatalog
from core.tenancy.normalization import normalize_tenant_id


@dataclass(frozen=True)
class OfferCatalogKey:
    tenant_id: str
    product_id: str
    environment: str = "prod"


@dataclass(frozen=True)
class OfferCatalogDirectives:
    """Canonical product/catalog extraction.

    This object exists to keep *one* real logic layer for product-level catalog
    resolution. Thin adapters may call into it, but they must not re-parse
    product/context/catalog fields differently.
    """

    tenant_id: str
    product_id: str
    environment: str
    catalog_id: str
    catalog_ref: str
    catalog_file: str


class OfferCatalogResolver:
    """Canonical resolver: tenant + product + env -> OfferCatalog.

    Resolver is offers-only and uses OfferCatalogRegistry with lazy factories.
    It is the single real logic layer for:
      - tenant/product/env candidate resolution
      - file-override resolution
      - registry fallback resolution
      - product/context field parsing for offer-catalog lookup

    Thin adapters may delegate to it, but must not duplicate its lookup logic.
    """

    def __init__(self, *, catalogs: OfferCatalogRegistry | None = None) -> None:
        self._catalogs = catalogs or default_offer_catalog_registry()

    def _candidate_catalog_ids(self, *, tenant: str, product: str, environment: str) -> list[str]:
        return product_catalog_candidates(tenant_id=tenant, product_id=product, environment=environment)

    def resolve(self, *, key: OfferCatalogKey) -> OfferCatalog:
        tenant = normalize_tenant_id(key.tenant_id)
        product = str(key.product_id or "").strip()
        env = str(key.environment or "prod").strip() or "prod"
        if not product:
            raise ValueError("product_id is required")

        last_err: Exception | None = None
        candidates = self._candidate_catalog_ids(tenant=tenant, product=product, environment=env)
        for catalog_id in candidates:
            try:
                return self._catalogs.get(catalog_id)
            except Exception as exc:
                last_err = exc
        raise KeyError(
            f"Offer catalog not found for tenant={tenant or '<none>'}, product={product}, env={env}. "
            f"Tried: {candidates}. Last error: {type(last_err).__name__ if last_err is not None else None}"
        )

    def resolve_registry_catalog(self, *, catalog_id: str) -> OfferCatalog:
        resolved_catalog_id = normalize_catalog_id(catalog_id)
        try:
            return self._catalogs.get(resolved_catalog_id)
        except (KeyError, ValueError):
            return self._catalogs.get(LEGACY_OFFER_CATALOG_ID)

    def resolve_yaml_override(self, *, catalog_file: str) -> OfferCatalog | None:
        filename = str(catalog_file or "").strip()
        if not filename:
            return None
        root = Path(__file__).resolve().parents[2]
        offers_dir = env_path("OFFER_CATALOGS_DIR", str(root / "products" / "offer_catalogs")).resolve()
        try:
            spec = load_yaml_offer_catalog_spec(base_dir=offers_dir, filename=filename)
        except (FileNotFoundError, ValueError):
            return None
        return YamlOfferCatalogV1.from_spec(spec)

    def read_directives(
        self,
        *,
        product: Mapping[str, Any],
        tenant_id: str | None,
        context: Mapping[str, Any] | None,
    ) -> OfferCatalogDirectives:
        prod = dict(product or {})
        ctx = dict(context or {})
        offer_catalog = prod.get("offer_catalog") if isinstance(prod.get("offer_catalog"), dict) else {}
        params = offer_catalog.get("params") if isinstance(offer_catalog.get("params"), dict) else {}
        return OfferCatalogDirectives(
            tenant_id=normalize_tenant_id(tenant_id or ctx.get("tenant_id")),
            product_id=str(prod.get("product_id") or prod.get("id") or "").strip(),
            environment=str(prod.get("environment") or ctx.get("environment") or "prod").strip() or "prod",
            catalog_id=normalize_catalog_id(offer_catalog.get("id")),
            catalog_ref=str(prod.get("offer_catalog_ref") or "").strip(),
            catalog_file=str((params or {}).get("catalog_file") or "").strip(),
        )

    def resolve_from_product(
        self,
        *,
        product: Mapping[str, Any],
        tenant_id: str | None,
        context: Mapping[str, Any] | None,
    ) -> OfferCatalog:
        directives = self.read_directives(product=product, tenant_id=tenant_id, context=context)
        if directives.catalog_ref:
            try:
                return self.resolve_registry_catalog(catalog_id=directives.catalog_ref)
            except (KeyError, ValueError):
                pass

        if directives.tenant_id and directives.product_id:
            try:
                return self.resolve(
                    key=OfferCatalogKey(
                        tenant_id=directives.tenant_id,
                        product_id=directives.product_id,
                        environment=directives.environment,
                    )
                )
            except (KeyError, ValueError):
                pass

        yaml_override = self.resolve_yaml_override(catalog_file=directives.catalog_file)
        if yaml_override is not None:
            return yaml_override

        return self.resolve_registry_catalog(catalog_id=directives.catalog_id)

    def resolve_for_product(
        self,
        *,
        product: Mapping[str, Any],
        tenant_id: str | None,
        context: Mapping[str, Any] | None,
    ) -> OfferCatalog:
        """Compatibility alias for older call-sites and tests.

        Canonical product-level resolution lives in resolve_from_product.
        """
        return self.resolve_from_product(product=product, tenant_id=tenant_id, context=context)
