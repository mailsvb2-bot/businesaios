"""Pricing governance I/O and validation. Executed ONLY via RuntimeExecutor.

Pricing data belongs to the tenant/product offer catalog. This module mutates
that canonical document atomically; it does not maintain a second global plans
file or pricing-version sidecar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.yaml_loader_shared import invalidate_yaml_cache, load_yaml
from core.offers.catalog_identity import catalog_registry_key
from core.offers.catalogs.yaml_schema import validate_yaml_offer_catalog_spec
from runtime.platform.config.env_flags import env_bool, env_path, env_str


def validate_pricing_change(
    *,
    admin_id: str,
    requested_by: str | None,
    pricing_version: str,
) -> None:
    """Raise RuntimeError if governance validation fails."""

    requested = str(requested_by or "").strip()
    if requested and requested == str(admin_id):
        allow = env_bool("ALLOW_SELF_APPROVE", False)
        if not allow:
            raise RuntimeError("SELF_APPROVAL_FORBIDDEN")

    version = str(pricing_version or "").strip()
    if not version:
        raise RuntimeError("PRICING_VERSION_REQUIRED")

    if env_bool("PRODUCTION_STRICT_MODE", False):
        lowered = version.lower().strip()
        if lowered in {"v1", "1", "default"} or lowered.startswith("v1."):
            raise RuntimeError("PRICING_VERSION_LOOKS_DEFAULT")


def _scope_segment(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"{field.upper()}_REQUIRED")
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise RuntimeError(f"INVALID_{field.upper()}")
    return text


def runtime_environment(value: str | None = None) -> str:
    text = str(value or env_str("APP_ENV", env_str("ENV", "dev")) or "dev").strip().lower()
    if text == "production":
        return "prod"
    if text == "development":
        return "dev"
    return text or "dev"


def canonical_catalog_path(
    *,
    tenant_id: str,
    product_id: str,
    environment: str | None = None,
    catalog_root: Path | None = None,
) -> Path:
    tenant = _scope_segment(tenant_id, field="tenant_id")
    product = _scope_segment(product_id, field="product_id")
    env = _scope_segment(runtime_environment(environment), field="environment")
    repo_root = Path(__file__).resolve().parents[3]
    root = (
        catalog_root
        or env_path(
            "OFFER_CATALOGS_DATA_DIR",
            str(repo_root / "data" / "offer_catalogs"),
        )
    ).expanduser().resolve()
    path = (root / tenant / product / f"{env}.yaml").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("CATALOG_PATH_ESCAPES_ROOT") from exc
    return path


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to persist offer catalogs") from exc
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _matches_offer(*, offer: dict[str, Any], offer_id: str | None, plan_id: int | None) -> bool:
    current_offer_id = str(offer.get("offer_id") or "").strip()
    if offer_id and current_offer_id == str(offer_id).strip():
        return True
    if plan_id is None:
        return False
    if current_offer_id == str(int(plan_id)):
        return True
    meta = offer.get("meta") if isinstance(offer.get("meta"), dict) else {}
    try:
        return int(meta.get("plan_id")) == int(plan_id)
    except (TypeError, ValueError):
        return False


@dataclass
class PricingChangeTransaction:
    catalog_path: Path
    catalog_tmp: Path
    original_catalog: bytes
    result: dict[str, Any]
    applied: bool = False
    finalized: bool = False

    def apply(self) -> dict[str, Any]:
        if self.finalized:
            raise RuntimeError("PRICING_TRANSACTION_FINALIZED")
        if self.applied:
            return dict(self.result)
        try:
            self.catalog_tmp.replace(self.catalog_path)
            invalidate_yaml_cache(self.catalog_path)
        except Exception as exc:
            try:
                self.rollback()
            except Exception as rollback_exc:
                raise RuntimeError(
                    f"PRICING_ROLLBACK_FAILED:{rollback_exc.__class__.__name__}:{rollback_exc}"
                ) from exc
            raise RuntimeError(f"PRICING_COMMIT_FAILED:{exc.__class__.__name__}:{exc}") from exc
        self.applied = True
        return dict(self.result)

    def rollback(self) -> None:
        if self.finalized:
            raise RuntimeError("PRICING_TRANSACTION_FINALIZED")
        restore_tmp = self.catalog_path.with_suffix(self.catalog_path.suffix + ".rollback.tmp")
        restore_tmp.write_bytes(self.original_catalog)
        restore_tmp.replace(self.catalog_path)
        invalidate_yaml_cache(self.catalog_path)
        self.applied = False
        self._cleanup_temps()

    def finalize(self) -> None:
        self._cleanup_temps()
        self.finalized = True

    def _cleanup_temps(self) -> None:
        self.catalog_tmp.unlink(missing_ok=True)
        self.catalog_path.with_suffix(self.catalog_path.suffix + ".rollback.tmp").unlink(missing_ok=True)


def prepare_offer_price_update(
    *,
    tenant_id: str,
    product_id: str,
    new_price: int,
    pricing_version: str,
    environment: str | None = None,
    offer_id: str | None = None,
    plan_id: int | None = None,
    catalog_path: Path | None = None,
) -> PricingChangeTransaction:
    tenant = _scope_segment(tenant_id, field="tenant_id")
    product = _scope_segment(product_id, field="product_id")
    env = runtime_environment(environment)
    price = int(new_price)
    if price <= 0:
        raise RuntimeError("NEW_PRICE_MUST_BE_POSITIVE")
    version = str(pricing_version or "").strip()
    if not version:
        raise RuntimeError("PRICING_VERSION_REQUIRED")
    selected_offer_id = str(offer_id or "").strip() or None
    selected_plan_id = int(plan_id) if plan_id is not None else None
    if selected_offer_id is None and selected_plan_id is None:
        raise RuntimeError("OFFER_ID_OR_PLAN_ID_REQUIRED")

    path = (
        catalog_path.expanduser().resolve()
        if catalog_path is not None
        else canonical_catalog_path(
            tenant_id=tenant,
            product_id=product,
            environment=env,
        )
    )
    if not path.exists():
        raise RuntimeError(f"OFFER_CATALOG_NOT_FOUND:{path}")

    original_catalog = path.read_bytes()
    try:
        spec = load_yaml(path, allow_empty=False, cache=False)
    except Exception as exc:
        raise RuntimeError(f"OFFER_CATALOG_READ_FAILED:{exc}") from exc

    catalog_id = catalog_registry_key(
        tenant_id=tenant,
        product_id=product,
        environment=env,
    )
    spec = dict(spec)
    spec.setdefault("catalog_id", catalog_id)
    validate_yaml_offer_catalog_spec(spec)

    offers = spec.get("offers")
    if not isinstance(offers, list):
        raise RuntimeError("OFFER_CATALOG_OFFERS_INVALID")
    matched_offer_id = ""
    old_price: int | None = None
    for raw_offer in offers:
        if not isinstance(raw_offer, dict):
            continue
        if not _matches_offer(
            offer=raw_offer,
            offer_id=selected_offer_id,
            plan_id=selected_plan_id,
        ):
            continue
        matched_offer_id = str(raw_offer.get("offer_id") or "").strip()
        old_price = int(raw_offer.get("base_price_rub"))
        raw_offer["base_price_rub"] = price
        break
    if not matched_offer_id:
        selector = selected_offer_id or str(selected_plan_id)
        raise RuntimeError(f"OFFER_NOT_FOUND:{selector}")

    spec["pricing_version"] = version
    validate_yaml_offer_catalog_spec(spec)

    tmp = path.with_suffix(path.suffix + ".pricing.tmp")
    tmp.unlink(missing_ok=True)
    try:
        _dump_yaml(tmp, spec)
        prepared = load_yaml(tmp, allow_empty=False, cache=False)
        validate_yaml_offer_catalog_spec(prepared)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"PRICING_PREPARE_FAILED:{exc.__class__.__name__}:{exc}") from exc

    return PricingChangeTransaction(
        catalog_path=path,
        catalog_tmp=tmp,
        original_catalog=original_catalog,
        result={
            "tenant_id": tenant,
            "product_id": product,
            "environment": env,
            "catalog_id": str(spec.get("catalog_id") or catalog_id),
            "offer_id": matched_offer_id,
            "plan_id": selected_plan_id,
            "old_price": old_price,
            "new_price": price,
            "pricing_version": version,
            "catalog_path": str(path),
        },
    )


def execute_offer_price_update(**kwargs: Any) -> dict[str, Any]:
    """Compatibility entrypoint for an immediate canonical catalog commit."""

    transaction = prepare_offer_price_update(**kwargs)
    try:
        return transaction.apply()
    finally:
        transaction.finalize()


__all__ = [
    "PricingChangeTransaction",
    "canonical_catalog_path",
    "execute_offer_price_update",
    "prepare_offer_price_update",
    "runtime_environment",
    "validate_pricing_change",
]
