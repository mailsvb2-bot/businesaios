from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path

from contracts.product_contract import OfferCatalog, ProductOffer
from core.offers.catalogs.yaml_catalog_loader import load_yaml_offer_catalog_spec
from runtime.platform.config.yaml_loader import load_yaml

CANON_PRODUCT_OFFER_PROJECTION = True


class OfferCatalogResolutionError(RuntimeError):
    pass


def _fail(code: str) -> None:
    raise OfferCatalogResolutionError(code)


def _mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(code)
    return value


def _minor(value: object, offer_id: str) -> int:
    try:
        rub = Decimal(str(value))
        minor = rub * 100
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OfferCatalogResolutionError(f"BAD_OFFER_PRICE:{offer_id}") from exc
    if not rub.is_finite() or rub < 0 or minor != minor.to_integral_value():
        _fail(f"BAD_OFFER_PRICE:{offer_id}")
    return int(minor)


def _descriptor(path: Path, code: str) -> Mapping[str, object]:
    try:
        return _mapping(load_yaml(path), code)
    except OfferCatalogResolutionError:
        raise
    except (OSError, ValueError) as exc:
        raise OfferCatalogResolutionError(code) from exc


def _external(raw: Mapping[str, object], root: Path, ref: str) -> OfferCatalog:
    parts = tuple(part.strip() for part in ref.split(":"))
    if len(parts) != 3 or not all(parts):
        _fail("BAD_OFFER_CATALOG_REF")
    namespace, product_id, environment = parts
    actual = str(raw.get("product_id") or "").strip()
    domain = str(raw.get("domain") or "").strip()
    actual_env = str(raw.get("environment") or "prod").strip() or "prod"
    if namespace != "default":
        _fail(f"UNSUPPORTED_OFFER_CATALOG_NAMESPACE:{namespace}")
    if not actual or not domain:
        _fail("BAD_PRODUCT_CONTRACT_FOR_OFFER_CATALOG")
    if product_id != actual:
        _fail(f"OFFER_CATALOG_REF_PRODUCT_MISMATCH:{product_id}:{actual}")
    if environment != actual_env:
        _fail(f"OFFER_CATALOG_REF_ENVIRONMENT_MISMATCH:{environment}:{actual_env}")

    root = root.resolve()
    descriptor_path = (root / f"{domain}.yaml").resolve()
    catalog_root = (root / "offer_catalogs").resolve()
    if descriptor_path.parent != root or catalog_root.parent != root:
        _fail("BAD_OFFER_CATALOG_DOMAIN")
    if not descriptor_path.is_file():
        _fail(f"PRODUCT_DESCRIPTOR_NOT_FOUND:{domain}")
    descriptor = _descriptor(descriptor_path, f"BAD_PRODUCT_DESCRIPTOR:{domain}")
    owner = str(descriptor.get("product_id") or "").strip()
    if owner != product_id or str(descriptor.get("domain") or "").strip() != domain:
        _fail(f"OFFER_CATALOG_DOMAIN_PRODUCT_MISMATCH:{domain}:{owner}:{product_id}")
    try:
        payload = load_yaml_offer_catalog_spec(base_dir=catalog_root, filename=f"{domain}.yaml", strict=False)
    except FileNotFoundError as exc:
        raise OfferCatalogResolutionError(f"OFFER_CATALOG_NOT_FOUND:{ref}") from exc
    except (OSError, ValueError) as exc:
        raise OfferCatalogResolutionError(f"BAD_OFFER_CATALOG:{ref}") from exc

    catalog_id, items = str(payload.get("catalog_id") or "").strip(), payload.get("offers")
    if not catalog_id or not isinstance(items, list) or not items:
        _fail(f"BAD_OFFER_CATALOG:{ref}")
    offers: list[ProductOffer] = []
    for raw_offer in items:
        item = _mapping(raw_offer, f"BAD_OFFER_CATALOG_ENTRY:{ref}")
        offer_id = str(item.get("offer_id") or "").strip()
        if not offer_id or "base_price_rub" not in item:
            _fail(f"BAD_OFFER_CATALOG_ENTRY:{ref}")
        structured = {
            name: {} if item.get(name) is None else dict(_mapping(item[name], f"BAD_OFFER_CATALOG_FIELD:{offer_id}:{name}"))
            for name in ("rules", "variants", "meta")
        }
        declared = str(structured["meta"].get("product") or "").strip()
        if declared and declared != product_id:
            _fail(f"OFFER_CATALOG_PRODUCT_MISMATCH:{offer_id}:{declared}:{product_id}")
        variants = structured["variants"]
        candidates = [variants.get("a"), *variants.values()]
        title = next(
            (str(value.get("title") or "").strip() for value in candidates if isinstance(value, Mapping) and str(value.get("title") or "").strip()),
            "",
        )
        period = item.get("period_days")
        try:
            period_days = None if period is None else int(period)
        except (TypeError, ValueError) as exc:
            raise OfferCatalogResolutionError(f"BAD_OFFER_PERIOD:{offer_id}") from exc
        if period_days is not None and period_days <= 0:
            _fail(f"BAD_OFFER_PERIOD:{offer_id}")
        offers.append(
            ProductOffer(
                offer_id=offer_id,
                title=str(item.get("title") or "").strip() or title or offer_id,
                price_minor=_minor(item["base_price_rub"], offer_id),
                currency="RUB",
                period_days=period_days,
                metadata={"offer_catalog_ref": ref, **structured},
            )
        )
    catalog = OfferCatalog(catalog_id=catalog_id, offers=tuple(offers))
    catalog.validate()
    return catalog


def _legacy(raw: Mapping[str, object]) -> OfferCatalog:
    raw_catalog = raw.get("offer_catalog")
    catalog_data = raw_catalog if isinstance(raw_catalog, dict) else {}
    offers: list[ProductOffer] = []
    raw_offers = catalog_data.get("offers") if isinstance(catalog_data.get("offers"), list) else []
    for item in raw_offers:
        if not isinstance(item, dict) or not str(item.get("offer_id") or "").strip():
            continue
        try:
            price = int(item.get("price_minor") or 0)
            period = None if item.get("period_days") is None else int(item["period_days"])
        except (TypeError, ValueError):
            price, period = 0, None
        tags = item.get("tags")
        offers.append(
            ProductOffer(
                offer_id=str(item["offer_id"]).strip(),
                title=str(item.get("title") or item["offer_id"]).strip(),
                price_minor=price,
                currency=str(item.get("currency") or "RUB").strip() or "RUB",
                period_days=period,
                tags=tuple(str(value) for value in tags if str(value)) if isinstance(tags, list | tuple) else (),
                metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            )
        )
    catalog = OfferCatalog(
        catalog_id=str(catalog_data.get("catalog_id") or raw.get("product_id") or "catalog"),
        offers=tuple(offers or [ProductOffer(offer_id="basic", title="Basic", price_minor=490_000, currency="RUB")]),
    )
    catalog.validate()
    return catalog


def resolve_offer_catalog(raw: Mapping[str, object], *, base_dir: Path | None = None) -> OfferCatalog:
    ref = str(raw.get("offer_catalog_ref") or "").strip()
    return _external(raw, base_dir or Path(__file__).parent, ref) if ref else _legacy(raw)


__all__ = ["CANON_PRODUCT_OFFER_PROJECTION", "OfferCatalogResolutionError", "resolve_offer_catalog"]
