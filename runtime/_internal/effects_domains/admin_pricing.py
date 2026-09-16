"""Pricing governance I/O and validation. Executed ONLY via RuntimeExecutor.

Pricing data belongs to the tenant/product offer catalog. Semantic pricing
validation stays here; durable catalog mutation mechanics have one canonical owner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config.yaml_loader_shared import load_yaml
from core.offers.catalog_identity import catalog_registry_key
from core.offers.catalogs.yaml_schema import validate_yaml_offer_catalog_spec
from runtime._internal.offer_catalog_mutation import (
    CatalogMutationTransaction,
    acquire_catalog_lock,
    digest_bytes,
    dump_yaml,
    file_digest,
    runtime_environment,
    scope_segment,
)
from runtime._internal.offer_catalog_mutation import (
    canonical_catalog_path as _canonical_catalog_path,
)
from runtime.platform.config.env_flags import env_bool, env_path

PricingChangeTransaction = CatalogMutationTransaction


def canonical_catalog_path(
    *,
    tenant_id: str,
    product_id: str,
    environment: str | None = None,
    catalog_root: Path | None = None,
) -> Path:
    """Compatibility seam over the canonical mutation owner's path resolver."""

    root = catalog_root
    if root is None:
        repo_root = Path(__file__).resolve().parents[3]
        root = env_path(
            "OFFER_CATALOGS_DATA_DIR",
            str(repo_root / "data" / "offer_catalogs"),
        )
    return _canonical_catalog_path(
        tenant_id=tenant_id,
        product_id=product_id,
        environment=environment,
        catalog_root=root,
    )


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
    lock_timeout_s: float | None = None,
) -> PricingChangeTransaction:
    tenant = scope_segment(tenant_id, field="tenant_id")
    product = scope_segment(product_id, field="product_id")
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
    mutation_lock = acquire_catalog_lock(
        path,
        timeout_s=lock_timeout_s,
    )
    tmp = path.with_suffix(path.suffix + ".pricing.tmp")
    try:
        if not path.exists():
            raise RuntimeError(f"OFFER_CATALOG_NOT_FOUND:{path}")

        original_catalog = path.read_bytes()
        original_digest = digest_bytes(original_catalog)
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
            matched_offer_id = str(
                raw_offer.get("offer_id") or ""
            ).strip()
            old_price = int(raw_offer.get("base_price_rub"))
            raw_offer["base_price_rub"] = price
            break
        if not matched_offer_id:
            selector = selected_offer_id or str(selected_plan_id)
            raise RuntimeError(f"OFFER_NOT_FOUND:{selector}")

        spec["pricing_version"] = version
        validate_yaml_offer_catalog_spec(spec)

        tmp.unlink(missing_ok=True)
        try:
            dump_yaml(tmp, spec)
            prepared = load_yaml(
                tmp,
                allow_empty=False,
                cache=False,
            )
            validate_yaml_offer_catalog_spec(prepared)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(
                f"PRICING_PREPARE_FAILED:{exc.__class__.__name__}:{exc}"
            ) from exc
        prepared_digest = file_digest(tmp)

        return PricingChangeTransaction(
            catalog_path=path,
            catalog_tmp=tmp,
            original_catalog=original_catalog,
            original_digest=original_digest,
            prepared_digest=prepared_digest,
            mutation_lock=mutation_lock,
            error_prefix="PRICING",
            result={
                "tenant_id": tenant,
                "product_id": product,
                "environment": env,
                "catalog_id": str(
                    spec.get("catalog_id") or catalog_id
                ),
                "offer_id": matched_offer_id,
                "plan_id": selected_plan_id,
                "old_price": old_price,
                "new_price": price,
                "pricing_version": version,
                "catalog_path": str(path),
                "catalog_revision_before": original_digest,
                "catalog_revision_after": prepared_digest,
            },
        )
    except Exception:
        tmp.unlink(missing_ok=True)
        mutation_lock.release()
        raise

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
