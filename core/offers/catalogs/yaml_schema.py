from __future__ import annotations

"""YAML offer catalog schema validation.

Goal:
- Fail fast in CI when catalogs are malformed.
- Keep runtime best-effort by default (no boot break).

Strict mode:
- Enabled when OFFER_CATALOGS_STRICT=1 or CI=1.
"""

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class SchemaError(Exception):
    code: str
    path: str = ""
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover
        p = f" at {self.path}" if self.path else ""
        d = f": {self.detail}" if self.detail else ""
        return f"{self.code}{p}{d}"


def _is_str(x: Any) -> bool:
    return isinstance(x, str) and bool(str(x).strip())


def validate_yaml_offer_catalog_spec(spec: Mapping[str, Any]) -> None:
    """Validate canonical YAML catalog spec used by YamlOfferCatalogV1.

    Expected minimal shape:
      catalog_id: str
      offers: list[{
        offer_id: str,
        base_price_rub: int,
        rules: {min_engagement?, max_fatigue?, cooldown_hours?},
        variants: {<key>: {title?, body?}},
        meta?: dict
      }]

    We allow extra keys.
    """

    if not isinstance(spec, Mapping):
        raise SchemaError("SPEC_NOT_MAPPING")

    cid = spec.get("catalog_id")
    if not _is_str(cid):
        raise SchemaError("MISSING_catalog_id", path="catalog_id")

    offers = spec.get("offers")
    if not isinstance(offers, list) or not offers:
        raise SchemaError("MISSING_offers", path="offers")

    for i, o in enumerate(offers):
        path0 = f"offers[{i}]"
        if not isinstance(o, Mapping):
            raise SchemaError("OFFER_NOT_MAPPING", path=path0)

        oid = o.get("offer_id")
        if not _is_str(oid):
            raise SchemaError("MISSING_offer_id", path=f"{path0}.offer_id")

        bpr = o.get("base_price_rub")
        if not isinstance(bpr, int):
            # allow numeric strings but not floats
            if isinstance(bpr, str) and bpr.strip().isdigit():
                pass
            else:
                raise SchemaError("BAD_base_price_rub", path=f"{path0}.base_price_rub")

        rules = o.get("rules")
        if rules is not None and not isinstance(rules, Mapping):
            raise SchemaError("BAD_rules", path=f"{path0}.rules")

        variants = o.get("variants")
        if variants is not None and not isinstance(variants, Mapping):
            raise SchemaError("BAD_variants", path=f"{path0}.variants")

        if isinstance(variants, Mapping):
            ok_any = False
            for vk, vv in variants.items():
                if not _is_str(vk):
                    raise SchemaError("BAD_variant_key", path=f"{path0}.variants")
                if not isinstance(vv, Mapping):
                    raise SchemaError("BAD_variant", path=f"{path0}.variants.{vk}")
                # title/body are optional, but if present must be strings
                for k in ("title", "body"):
                    if k in vv and not isinstance(vv.get(k), str):
                        raise SchemaError("BAD_variant_field", path=f"{path0}.variants.{vk}.{k}")
                ok_any = True
            if not ok_any:
                raise SchemaError("EMPTY_variants", path=f"{path0}.variants")

        meta = o.get("meta")
        if meta is not None and not isinstance(meta, Mapping):
            raise SchemaError("BAD_meta", path=f"{path0}.meta")


def validate_data_catalog_dict(cat: Mapping[str, Any]) -> None:
    """Validate simple data-only catalogs used by tenant/product resolver.

    We do NOT enforce a particular offer shape; only require a mapping.
    """
    if not isinstance(cat, Mapping):
        raise SchemaError("CATALOG_NOT_MAPPING")
