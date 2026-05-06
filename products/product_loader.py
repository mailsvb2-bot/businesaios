from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contracts.economics_config import EconomicsConfigV1
from contracts.product_contract import (
    EntryPolicy,
    EntitlementsSpec,
    ModuleSpec,
    ModulesSpec,
    ProductContract,
)
from runtime.platform.config.env_flags import env_str
from runtime.platform.config.yaml_loader import load_yaml
from products.offer_catalog_resolver import resolve_offer_catalog
from products.pricing_models import resolve_pricing_model
from products.telemetry_schemas import resolve_telemetry_schema


@dataclass(frozen=True)
class ProductLoader:
    base_dir: Path

    def load(self, filename: str) -> ProductContract:
        products_dir = self.base_dir.resolve()
        path = (products_dir / filename).resolve()
        if products_dir not in path.parents and path != products_dir:
            raise ValueError(f"PRODUCT_CONFIG must be within products/: {filename}")

        raw = load_yaml(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("BAD_PRODUCT_CONFIG")

        tenant_id = str(raw.get("tenant_id") or env_str("TENANT_ID") or "").strip()
        if not tenant_id:
            raise ValueError("MISSING_TENANT_ID")

        product_id = str(raw.get("product_id") or "").strip()
        domain = str(raw.get("domain") or "").strip()
        if not product_id or not domain:
            raise ValueError("BAD_PRODUCT_CONTRACT:missing product_id/domain")

        product_version = str(raw.get("product_version") or raw.get("version") or "v1").strip() or "v1"
        name = str(raw.get("name") or "").strip()
        environment = str(raw.get("environment") or "prod").strip() or "prod"
        autopilot_contract_ref = str(raw.get("autopilot_contract_ref") or "").strip()

        econ_raw = raw.get("economics") if isinstance(raw.get("economics"), dict) else {}
        economics = EconomicsConfigV1.from_dict(econ_raw)

        ep_raw = raw.get("entry_policy") if isinstance(raw.get("entry_policy"), dict) else {}
        entry = EntryPolicy(
            entrypoints=tuple(ep_raw.get("entrypoints") or ("telegram",)),
            default_entrypoint=str(ep_raw.get("default_entrypoint") or "telegram"),
            requires_auth=bool(ep_raw.get("requires_auth", True)),
            requires_entitlement=bool(ep_raw.get("requires_entitlement", False)),
            required_entitlements=tuple(ep_raw.get("required_entitlements") or ()),
        )

        offer_catalog = resolve_offer_catalog(raw)
        pricing_model = resolve_pricing_model(raw)
        telemetry_schema = resolve_telemetry_schema(raw)

        ent_raw = raw.get("entitlements") if isinstance(raw.get("entitlements"), dict) else {}
        ent = EntitlementsSpec(keys=tuple(ent_raw.get("keys") or ()))

        mods_raw = raw.get("modules") if isinstance(raw.get("modules"), dict) else {}
        modules = ModulesSpec(
            modules=tuple(
                ModuleSpec(
                    module_id=str(k),
                    enabled_by_default=bool(v) if isinstance(v, bool) else True,
                    config=(v if isinstance(v, dict) else {}),
                )
                for k, v in mods_raw.items()
            )
        )

        pc = ProductContract(
            tenant_id=tenant_id,
            product_id=product_id,
            domain=domain,
            product_version=product_version,
            name=name,
            environment=environment,
            entry_policy=entry,
            offer_catalog=offer_catalog,
            pricing_model=pricing_model,
            telemetry_schema=telemetry_schema,
            entitlements=ent,
            modules=modules,
            economics=economics,
            autopilot_contract_ref=autopilot_contract_ref,
        )
        pc.validate()
        return pc


def load_product_from_env() -> ProductContract:
    """Load product contract from env.

    PRODUCT_CONFIG=organization_platform.yaml (default)
    """

    cfg = env_str("PRODUCT_CONFIG", "organization_platform.yaml") or "organization_platform.yaml"
    loader = ProductLoader(base_dir=Path(__file__).parent)
    return loader.load(cfg)
