from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import yaml

from contracts.product_contract import Offer, OfferCatalog


class OfferCatalogResolutionError(RuntimeError):
    pass


def _fail(code: str) -> None:
    raise OfferCatalogResolutionError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(code)
    return value


def _yaml(path: Path, code: str) -> Mapping[str, Any]:
    try:
        return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), code)
    except OfferCatalogResolutionError:
        raise
    except (OSError, yaml.YAMLError) as exc:
        raise OfferCatalogResolutionError(code) from exc


def _minor(value: object, offer_id: str) -> int:
    try:
        rub = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OfferCatalogResolutionError(f"BAD_OFFER_PRICE:{offer_id}") from exc
    minor = rub * 100
    if not rub.is_finite() or rub < 0 or minor != minor.to_integral_value():
        _fail(f"BAD_OFFER_PRICE:{offer_id}")
    return int(minor)


def _external(raw: Mapping[str, Any], base_dir: Path, ref: str) -> OfferCatalog:
    parts = tuple(part.strip() for part in ref.split(":"))
    if len(parts) != 3 or not all(parts):
        _fail("BAD_OFFER_CATALOG_REF")
    namespace, product_id, environment = parts
    if namespace != "default":
        _fail(f"UNSUPPORTED_OFFER_CATALOG_NAMESPACE:{namespace}")
    actual_product = str(raw.get("product_id") or "").strip()
    domain = str(raw.get("domain") or "").strip()
    actual_environment = str(raw.get("environment") or "prod").strip() or "prod"
    if not actual_product or not domain:
        _fail("BAD_PRODUCT_CONTRACT_FOR_OFFER_CATALOG")
    if product_id != actual_product:
        _fail(f"OFFER_CATALOG_REF_PRODUCT_MISMATCH:{product_id}:{actual_product}")
    if environment != actual_environment:
        _fail(f"OFFER_CATALOG_REF_ENVIRONMENT_MISMATCH:{environment}:{actual_environment}")
    root = base_dir.resolve()
    descriptor_path = (root / f"{domain}.yaml").resolve()
    if descriptor_path.parent != root:
        _fail("BAD_OFFER_CATALOG_DOMAIN")
    if not descriptor_path.is_file():
        _fail(f"PRODUCT_DESCRIPTOR_NOT_FOUND:{domain}")
    descriptor = _yaml(descriptor_path, f"BAD_PRODUCT_DESCRIPTOR:{domain}")
    owner = str(descriptor.get("product_id") or "").strip()
    if owner != product_id or str(descriptor.get("domain") or "").strip() != domain:
        _fail(f"OFFER_CATALOG_DOMAIN_PRODUCT_MISMATCH:{domain}:{owner}:{product_id}")
    catalog_path = (root / "offer_catalogs" / f"{domain}.yaml").resolve()
    if catalog_path.parent != (root / "offer_catalogs").resolve():
        _fail("BAD_OFFER_CATALOG_DOMAIN")
    if not catalog_path.is_file():
        _fail(f"OFFER_CATALOG_NOT_FOUND:{ref}")
    payload = _yaml(catalog_path, f"BAD_OFFER_CATALOG:{ref}")
    catalog_id, items = str(payload.get("catalog_id") or "").strip(), payload.get("offers")
    if not catalog_id or not isinstance(items, list) or not items:
        _fail(f"BAD_OFFER_CATALOG:{ref}")
    offers: list[Offer] = []
    for raw_offer in items:
        item = _mapping(raw_offer, f"BAD_OFFER_CATALOG_ENTRY:{ref}")
        offer_id = str(item.get("offer_id") or "").strip()
        if not offer_id or "base_price_rub" not in item:
            _fail(f"BAD_OFFER_CATALOG_ENTRY:{ref}")
        structured = {name: {} if item.get(name) is None else _mapping(item[name], f"BAD_OFFER_CATALOG_FIELD:{offer_id}:{name}") for name in ("rules", "variants", "meta")}
        declared = str(structured["meta"].get("product") or "").strip()
        if declared and declared != product_id:
            _fail(f"OFFER_CATALOG_PRODUCT_MISMATCH:{offer_id}:{declared}:{product_id}")
        variants = structured["variants"]
        variant_title = next((str(v.get("title") or "").strip() for v in ([variants.get("a")] + list(variants.values())) if isinstance(v, Mapping) and str(v.get("title") or "").strip()), "")
        period = item.get("period_days")
        try:
            period_days = None if period is None else int(period)
        except (TypeError, ValueError) as exc:
            raise OfferCatalogResolutionError(f"BAD_OFFER_PERIOD:{offer_id}") from exc
        if period_days is not None and period_days <= 0:
            _fail(f"BAD_OFFER_PERIOD:{offer_id}")
        offers.append(Offer(offer_id=offer_id, title=str(item.get("title") or "").strip() or variant_title or offer_id, price_minor=_minor(item["base_price_rub"], offer_id), currency="RUB", period_days=period_days, metadata={"offer_catalog_ref": ref, **{k: dict(v) for k, v in structured.items()}}))
    catalog = OfferCatalog(catalog_id=catalog_id, offers=tuple(offers))
    catalog.validate()
    return catalog


def _legacy(raw: Mapping[str, Any]) -> OfferCatalog:
    oc = raw.get("offer_catalog") if isinstance(raw.get("offer_catalog"), dict) else {}
    offers = []
    for item in oc.get("offers") if isinstance(oc.get("offers"), list) else []:
        if not isinstance(item, dict) or not str(item.get("offer_id") or "").strip():
            continue
        try:
            price, period = int(item.get("price_minor") or 0), None if item.get("period_days") is None else int(item["period_days"])
        except (TypeError, ValueError):
            price, period = 0, None
        tags = item.get("tags")
        offers.append(Offer(offer_id=str(item["offer_id"]).strip(), title=str(item.get("title") or item["offer_id"]).strip(), price_minor=price, currency=str(item.get("currency") or "RUB").strip() or "RUB", period_days=period, tags=tuple(str(x) for x in tags if str(x)) if isinstance(tags, (list, tuple)) else (), metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {}))
    catalog = OfferCatalog(catalog_id=str(oc.get("catalog_id") or raw.get("product_id") or "catalog"), offers=tuple(offers or [Offer(offer_id="basic", title="Basic", price_minor=4900_00, currency="RUB")]))
    catalog.validate()
    return catalog


def resolve_offer_catalog(raw: Mapping[str, Any], *, base_dir: Path | None = None) -> OfferCatalog:
    ref = str(raw.get("offer_catalog_ref") or "").strip()
    return _external(raw, (base_dir or Path(__file__).parent).resolve(), ref) if ref else _legacy(raw)
