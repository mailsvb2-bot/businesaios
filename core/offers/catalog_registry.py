from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from config.env_flags import env_bool, env_path
from config.yaml_loader_shared import load_yaml
from core.observability.silent import swallow
from core.offers.catalog_identity import (
    LEGACY_OFFER_CATALOG_ID,
    NONE_OFFER_CATALOG_ID,
    catalog_registry_key,
    normalize_catalog_id,
)
from core.offers.catalogs.none_catalog import NoneOfferCatalogV1

# IMPORTANT:
# Keep imports here offers-only. Do NOT import retention engines/adapters.
from core.offers.catalogs.retention_catalog import LegacyOfferCatalogV1
from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1
from core.offers.catalogs.yaml_catalog_loader import YamlOfferCatalogLoaderV1
from core.offers.catalogs.yaml_schema import validate_yaml_offer_catalog_spec
from core.offers.offer_types import OfferCatalog
from core.offers.yaml_offer_catalog_loader import YamlOfferCatalogLoader  # legacy loader (kept)

log = logging.getLogger("core.offers")

CatalogFactory = Callable[[], OfferCatalog]


@dataclass
class OfferCatalogRegistry:
    """Offer catalog registry.

    Supports lazy factories to avoid heavy import-time work and prevent cycles.
    """

    _by_id: dict[str, OfferCatalog | CatalogFactory]
    _cache: dict[str, OfferCatalog] = field(default_factory=dict)

    def register(self, catalog: OfferCatalog) -> None:
        self._by_id[str(catalog.id)] = catalog
        self._cache[str(catalog.id)] = catalog

    def register_factory(self, catalog_id: str, factory: CatalogFactory) -> None:
        cid = str(catalog_id or "").strip()
        if not cid:
            raise ValueError("catalog_id is required")
        self._by_id[cid] = factory
        # Do not populate cache.

    def get(self, catalog_id: str) -> OfferCatalog:
        cid = normalize_catalog_id(catalog_id)
        if cid in self._cache:
            return self._cache[cid]
        if cid not in self._by_id:
            raise KeyError(f"unknown offer catalog: {cid}")
        v = self._by_id[cid]
        if callable(v):
            cat = v()
        else:
            cat = v
        self._cache[cid] = cat
        return cat


def default_offer_catalog_registry() -> OfferCatalogRegistry:
    reg = OfferCatalogRegistry(_by_id={})

    repo_root = Path(__file__).resolve().parents[2]

    strict_mode = env_bool("OFFER_CATALOGS_STRICT", False) or env_bool("CI", False)

    # Built-ins are registered lazily (cheap + cycle-safe).
    reg.register_factory(LEGACY_OFFER_CATALOG_ID, lambda: LegacyOfferCatalogV1())
    reg.register_factory(NONE_OFFER_CATALOG_ID, lambda: NoneOfferCatalogV1())

    # Best-effort: load engine-level YAML catalogs from products/offer_catalogs/*.yaml.
    # NOTE: We load them eagerly because we must discover their catalog_id.
    try:
        base = repo_root / "products" / "offer_catalogs"
        loader = YamlOfferCatalogLoaderV1(base_dir=base)
        for _cid, cat in (loader.load_all() or {}).items():
            reg.register(cat)

        # Backward compatibility: also try legacy path products/offers/*.yaml.
        legacy_base = repo_root / "products" / "offers"
        legacy_loader = YamlOfferCatalogLoader(base_dir=legacy_base)
        for cid, spec in (legacy_loader.load_all() or {}).items():
            try:
                reg._by_id.setdefault(str(cid), YamlOfferCatalogV1.from_spec(spec))
            except Exception as e:
                log.warning("failed to load legacy offer catalog %s: %r", cid, e)
    except Exception as e:
        # Never break boot if offers are missing (unless strict).
        if strict_mode:
            raise
        try:
            log.warning("offer_catalog_registry: failed to load built-in YAML catalogs: %r", e)
        except Exception:
            swallow(__name__, 'core/offers/catalog_registry.py')

    # Product-scoped YAML catalogs (tenant/product/env) loaded lazily.
    # Layout:
    #   data/offer_catalogs/<tenant>/<product>/<env>.yaml
    # Example catalog_id in registry: "tenantA:organization_platform:prod".
    # Env override (tests): OFFER_CATALOGS_DATA_DIR
    try:
        data_dir = env_path("OFFER_CATALOGS_DATA_DIR", str(repo_root / "data" / "offer_catalogs")).resolve()
        if data_dir.exists() and data_dir.is_dir():
            for tenant_dir in sorted([p for p in data_dir.iterdir() if p.is_dir()]):
                tenant = tenant_dir.name
                for product_dir in sorted([p for p in tenant_dir.iterdir() if p.is_dir()]):
                    product = product_dir.name
                    for y in sorted(product_dir.glob("*.y*ml")):
                        env = y.stem
                        tenant_key = str(tenant or "").strip()
                        if not tenant_key:
                            continue
                        if tenant_key.lower() == "default":
                            cid = f"default:{product}:{env}"
                        else:
                            cid = catalog_registry_key(tenant_id=tenant_key, product_id=product, environment=env)
                        if cid in reg._by_id:
                            continue

                        def _mk_factory(path: Path, catalog_id: str):
                            def _factory() -> OfferCatalog:
                                raw = load_yaml(path.read_text(encoding="utf-8"))
                                if not isinstance(raw, dict):
                                    raise ValueError("BAD_OFFER_CATALOG")
                                raw2 = dict(raw)
                                raw2.setdefault("catalog_id", catalog_id)

                                # Strict mode: validate schema early (CI).
                                if env_bool("OFFER_CATALOGS_STRICT", False) or env_bool("CI", False):
                                    validate_yaml_offer_catalog_spec(raw2)

                                return YamlOfferCatalogV1.from_spec(raw2)

                            return _factory

                        reg.register_factory(cid, _mk_factory(y, cid))
    except Exception as e:
        if strict_mode:
            raise
        try:
            log.warning("offer_catalog_registry: failed to scan data_dir catalogs: %r", e)
        except Exception:
            swallow(__name__, 'core/offers/catalog_registry.py')

    return reg
