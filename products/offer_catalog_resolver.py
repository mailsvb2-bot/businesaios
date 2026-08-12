from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import yaml

from contracts.product_contract import Offer, OfferCatalog


class OfferCatalogResolutionError(RuntimeError):
    """Raised when an explicit external offer catalog cannot be resolved safely."""


def _rub_to_minor(value: object, *, offer_id: str) -> int:
    try:
        rub = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OfferCatalogResolutionError(f"BAD_OFFER_PRICE:{offer_id}") from exc
    if not rub.is_finite() or rub < 0:
        raise OfferCatalogResolutionError(f"BAD_OFFER_PRICE:{offer_id}")
    minor = rub * 100
    if minor != minor.to_integral_value():
        raise OfferCatalogResolutionError(f"BAD_OFFER_PRICE_PRECISION:{offer_id}")
    return int(minor)


def _variant_title(variants: object) -> str:
    if not isinstance(variants, Mapping):
        return ""

    preferred = variants.get("a")
    candidates = [preferred, *variants.values()]
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        title = str(candidate.get("title") or "").strip()
        if title:
            return title
    return ""


def _optional_mapping_field(
    item: Mapping[str, Any],
    field_name: str,
    *,
    offer_id: str,
) -> Mapping[str, Any]:
    value = item.get(field_name)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise OfferCatalogResolutionError(
            f"BAD_OFFER_CATALOG_FIELD:{offer_id}:{field_name}"
        )
    return value


def _load_yaml_mapping(path: Path, *, error_code: str) -> Mapping[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise OfferCatalogResolutionError(error_code) from exc
    if not isinstance(payload, Mapping):
        raise OfferCatalogResolutionError(error_code)
    return payload


def _external_catalog_path(*, raw: Mapping[str, Any], base_dir: Path, ref: str) -> Path:
    parts = ref.split(":")
    if len(parts) != 3 or any(not part.strip() for part in parts):
        raise OfferCatalogResolutionError("BAD_OFFER_CATALOG_REF")

    namespace, ref_product_id, ref_environment = (part.strip() for part in parts)
    if namespace != "default":
        raise OfferCatalogResolutionError(f"UNSUPPORTED_OFFER_CATALOG_NAMESPACE:{namespace}")

    product_id = str(raw.get("product_id") or "").strip()
    environment = str(raw.get("environment") or "prod").strip() or "prod"
    domain = str(raw.get("domain") or "").strip()
    if not product_id or not domain:
        raise OfferCatalogResolutionError("BAD_PRODUCT_CONTRACT_FOR_OFFER_CATALOG")
    if ref_product_id != product_id:
        raise OfferCatalogResolutionError(
            f"OFFER_CATALOG_REF_PRODUCT_MISMATCH:{ref_product_id}:{product_id}"
        )
    if ref_environment != environment:
        raise OfferCatalogResolutionError(
            f"OFFER_CATALOG_REF_ENVIRONMENT_MISMATCH:{ref_environment}:{environment}"
        )

    root_dir = base_dir.resolve()
    descriptor_path = (root_dir / f"{domain}.yaml").resolve()
    if descriptor_path.parent != root_dir:
        raise OfferCatalogResolutionError("BAD_OFFER_CATALOG_DOMAIN")
    if not descriptor_path.is_file():
        raise OfferCatalogResolutionError(f"PRODUCT_DESCRIPTOR_NOT_FOUND:{domain}")

    descriptor = _load_yaml_mapping(
        descriptor_path,
        error_code=f"BAD_PRODUCT_DESCRIPTOR:{domain}",
    )
    descriptor_product_id = str(descriptor.get("product_id") or "").strip()
    descriptor_domain = str(descriptor.get("domain") or "").strip()
    if descriptor_product_id != ref_product_id or descriptor_domain != domain:
        raise OfferCatalogResolutionError(
            f"OFFER_CATALOG_DOMAIN_PRODUCT_MISMATCH:{domain}:{descriptor_product_id}:{ref_product_id}"
        )

    catalog_dir = (root_dir / "offer_catalogs").resolve()
    path = (catalog_dir / f"{domain}.yaml").resolve()
    if path.parent != catalog_dir:
        raise OfferCatalogResolutionError("BAD_OFFER_CATALOG_DOMAIN")
    if not path.is_file():
        raise OfferCatalogResolutionError(f"OFFER_CATALOG_NOT_FOUND:{ref}")
    return path


def _load_external_catalog(*, raw: Mapping[str, Any], base_dir: Path, ref: str) -> OfferCatalog:
    path = _external_catalog_path(raw=raw, base_dir=base_dir, ref=ref)
    payload = _load_yaml_mapping(path, error_code=f"BAD_OFFER_CATALOG:{ref}")

    catalog_id = str(payload.get("catalog_id") or "").strip()
    offers_raw = payload.get("offers")
    if not catalog_id or not isinstance(offers_raw, list) or not offers_raw:
        raise OfferCatalogResolutionError(f"BAD_OFFER_CATALOG:{ref}")

    ref_product_id = ref.split(":", 2)[1]
    offers: list[Offer] = []
    for item in offers_raw:
        if not isinstance(item, Mapping):
            raise OfferCatalogResolutionError(f"BAD_OFFER_CATALOG_ENTRY:{ref}")

        offer_id = str(item.get("offer_id") or "").strip()
        if not offer_id or "base_price_rub" not in item:
            raise OfferCatalogResolutionError(f"BAD_OFFER_CATALOG_ENTRY:{ref}")

        meta = _optional_mapping_field(item, "meta", offer_id=offer_id)
        declared_product = str(meta.get("product") or "").strip()
        if declared_product and declared_product != ref_product_id:
            raise OfferCatalogResolutionError(
                f"OFFER_CATALOG_PRODUCT_MISMATCH:{offer_id}:{declared_product}:{ref_product_id}"
            )

        variants = _optional_mapping_field(item, "variants", offer_id=offer_id)
        rules = _optional_mapping_field(item, "rules", offer_id=offer_id)
        title = str(item.get("title") or "").strip() or _variant_title(variants) or offer_id

        period_days: int | None = None
        if item.get("period_days") is not None:
            try:
                period_days = int(item["period_days"])
            except (TypeError, ValueError) as exc:
                raise OfferCatalogResolutionError(f"BAD_OFFER_PERIOD:{offer_id}") from exc
            if period_days <= 0:
                raise OfferCatalogResolutionError(f"BAD_OFFER_PERIOD:{offer_id}")

        offers.append(
            Offer(
                offer_id=offer_id,
                title=title,
                price_minor=_rub_to_minor(item["base_price_rub"], offer_id=offer_id),
                currency="RUB",
                period_days=period_days,
                metadata={
                    "offer_catalog_ref": ref,
                    "rules": dict(rules),
                    "variants": dict(variants),
                    "meta": dict(meta),
                },
            )
        )

    catalog = OfferCatalog(catalog_id=catalog_id, offers=tuple(offers))
    catalog.validate()
    return catalog


def _resolve_inline_or_legacy(raw: Mapping[str, Any]) -> OfferCatalog:
    oc = raw.get("offer_catalog") if isinstance(raw.get("offer_catalog"), dict) else {}
    cid = str(oc.get("catalog_id") or raw.get("product_id") or "catalog")
    offers_raw = oc.get("offers") if isinstance(oc.get("offers"), list) else []

    offers: list[Offer] = []
    for item in offers_raw:
        if not isinstance(item, dict):
            continue
        offer_id = str(item.get("offer_id") or "").strip()
        if not offer_id:
            continue
        title = str(item.get("title") or offer_id).strip() or offer_id
        try:
            price_minor = int(item.get("price_minor") or 0)
        except (TypeError, ValueError):
            price_minor = 0
        currency = str(item.get("currency") or "RUB").strip() or "RUB"
        period_days = None
        if "period_days" in item and item.get("period_days") is not None:
            try:
                period_days = int(item.get("period_days"))
            except (TypeError, ValueError):
                period_days = None
        tags = item.get("tags")
        tags_t = tuple(str(x) for x in (tags or ()) if str(x)) if isinstance(tags, (list, tuple)) else ()
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}

        offers.append(
            Offer(
                offer_id=offer_id,
                title=title,
                price_minor=price_minor,
                currency=currency,
                period_days=period_days,
                tags=tags_t,
                metadata=metadata,
            )
        )

    if not offers:
        # Compatibility only for legacy product configs that do not declare
        # offer_catalog_ref. An explicit external reference must never fall
        # back to a different commercial offer.
        offers = [Offer(offer_id="basic", title="Basic", price_minor=4900_00, currency="RUB")]

    catalog = OfferCatalog(catalog_id=cid, offers=tuple(offers))
    catalog.validate()
    return catalog


def resolve_offer_catalog(raw: Mapping[str, Any], *, base_dir: Path | None = None) -> OfferCatalog:
    """Resolve the product offer catalog without creating a second source of truth.

    An explicit ``offer_catalog_ref`` is authoritative and fail-closed. Legacy
    inline/fallback behavior remains available only when no external reference
    is declared.
    """

    ref = str(raw.get("offer_catalog_ref") or "").strip()
    if ref:
        return _load_external_catalog(
            raw=raw,
            base_dir=(base_dir or Path(__file__).parent).resolve(),
            ref=ref,
        )
    return _resolve_inline_or_legacy(raw)
