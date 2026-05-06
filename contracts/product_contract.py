from __future__ import annotations

"""Product Contract — Single Source of Truth.

Canonical definition of ProductContract for BusinesAIOS.

Design goals:
- Separate Engine from Products without forking code.
- Keep contract declarative (no embedded "brains").
- Provide stable interfaces for runtime wiring, offers/pricing, telemetry, entitlements.

Compatibility shims:
- `core.contracts.product_contract` and `core.products.product_contract` re-export this module.
  Lock-tests ensure this module remains the only definition site.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Set, Tuple

from contracts.economics_config import EconomicsConfigV1


@dataclass(frozen=True)
class EntryPolicy:
    """Defines how the product is entered (routing + access gates).

    Keep it declarative. Runtime wiring consumes it.
    """

    entrypoints: Tuple[str, ...]  # e.g. ("telegram", "webapp")
    default_entrypoint: str
    requires_auth: bool = True
    requires_entitlement: bool = False
    required_entitlements: Tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.entrypoints:
            raise ValueError("EntryPolicy.entrypoints must be non-empty")
        if self.default_entrypoint not in self.entrypoints:
            raise ValueError("EntryPolicy.default_entrypoint must be within entrypoints")
        if self.requires_entitlement and not self.required_entitlements:
            raise ValueError("EntryPolicy.requires_entitlement=True requires required_entitlements")


@dataclass(frozen=True)
class Offer:
    offer_id: str
    title: str
    price_minor: int  # cents/kopeks
    currency: str
    period_days: Optional[int] = None  # None for one-time
    tags: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OfferCatalog:
    """Declarative catalog: "what we can sell" (not how we decide)."""

    catalog_id: str
    offers: Tuple[Offer, ...]

    def validate(self) -> None:
        if not self.catalog_id:
            raise ValueError("OfferCatalog.catalog_id is required")
        seen: Set[str] = set()
        for o in self.offers:
            if not o.offer_id:
                raise ValueError("Offer.offer_id is required")
            if o.offer_id in seen:
                raise ValueError(f"Duplicate offer_id: {o.offer_id}")
            if int(o.price_minor) < 0:
                raise ValueError(f"Offer.price_minor must be >= 0 for offer_id={o.offer_id}")
            seen.add(o.offer_id)


class PricingModel(Protocol):
    """PricingModel decides which offer (or price) to use for a user context."""

    pricing_model_id: str

    def choose_offer_id(self, *, user_id: str, tenant_id: str, context: Mapping[str, Any]) -> str: ...


@dataclass(frozen=True)
class TelemetryField:
    name: str
    type: str  # "str" | "int" | "float" | "bool" | "json"
    required: bool = True


@dataclass(frozen=True)
class TelemetryEventSpec:
    event_type: str
    fields: Tuple[TelemetryField, ...]


@dataclass(frozen=True)
class TelemetrySchema:
    schema_id: str
    events: Tuple[TelemetryEventSpec, ...]

    def validate(self) -> None:
        if not self.schema_id:
            raise ValueError("TelemetrySchema.schema_id is required")
        etypes: Set[str] = set()
        for ev in self.events:
            if not ev.event_type:
                raise ValueError("TelemetryEventSpec.event_type is required")
            if ev.event_type in etypes:
                raise ValueError(f"Duplicate telemetry event_type: {ev.event_type}")
            etypes.add(ev.event_type)


@dataclass(frozen=True)
class EntitlementsSpec:
    """Declares entitlement keys used by this product."""

    keys: Tuple[str, ...]

    def validate(self) -> None:
        if len(set(self.keys)) != len(self.keys):
            raise ValueError("EntitlementsSpec.keys must be unique")


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    enabled_by_default: bool = True
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModulesSpec:
    modules: Tuple[ModuleSpec, ...]

    def validate(self) -> None:
        seen: Set[str] = set()
        for m in self.modules:
            if not m.module_id:
                raise ValueError("ModuleSpec.module_id is required")
            if m.module_id in seen:
                raise ValueError(f"Duplicate module_id: {m.module_id}")
            seen.add(m.module_id)


@dataclass(frozen=True)
class ProductContract:
    """Canonical interface for any product in BusinesAIOS."""

    tenant_id: str
    product_id: str
    domain: str

    product_version: str = "v1"
    name: str = ""
    environment: str = "prod"

    entry_policy: EntryPolicy = field(
        default_factory=lambda: EntryPolicy(entrypoints=("telegram",), default_entrypoint="telegram")
    )
    offer_catalog: OfferCatalog = field(
        default_factory=lambda: OfferCatalog(
            catalog_id="catalog",
            offers=(Offer(offer_id="basic", title="Basic", price_minor=0, currency="RUB"),),
        )
    )
    pricing_model: PricingModel = field(default_factory=lambda: _DefaultPricingModel())  # type: ignore[misc]
    telemetry_schema: TelemetrySchema = field(
        default_factory=lambda: TelemetrySchema(schema_id="telemetry_default@v1", events=())
    )
    entitlements: EntitlementsSpec = field(default_factory=lambda: EntitlementsSpec(keys=()))
    modules: ModulesSpec = field(default_factory=lambda: ModulesSpec(modules=()))

    economics: EconomicsConfigV1 = field(default_factory=EconomicsConfigV1)
    autopilot_contract_ref: str = ""

    def validate(self) -> None:
        tid = str(self.tenant_id or "").strip()
        if not tid:
            raise ValueError("tenant_id is required")
        if not str(self.product_id or "").strip():
            raise ValueError("product_id is required")
        if not str(self.domain or "").strip():
            raise ValueError("domain is required")
        if not str(self.product_version or "").strip():
            raise ValueError("product_version is required")

        self.entry_policy.validate()
        self.offer_catalog.validate()
        self.telemetry_schema.validate()
        self.entitlements.validate()
        self.modules.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "product_id": str(self.product_id),
            "product_version": str(self.product_version),
            "domain": str(self.domain),
            "name": str(self.name or ""),
            "environment": str(self.environment or "prod"),
            "entry_policy": {
                "entrypoints": tuple(self.entry_policy.entrypoints),
                "default_entrypoint": str(self.entry_policy.default_entrypoint),
                "requires_auth": bool(self.entry_policy.requires_auth),
                "requires_entitlement": bool(self.entry_policy.requires_entitlement),
                "required_entitlements": tuple(self.entry_policy.required_entitlements),
            },
            "modules": {m.module_id: bool(m.enabled_by_default) for m in (self.modules.modules or ())},
            "offer_catalog": {
                "catalog_id": str(self.offer_catalog.catalog_id),
                "offers": [
                    {
                        "offer_id": o.offer_id,
                        "title": o.title,
                        "price_minor": int(o.price_minor),
                        "currency": o.currency,
                        "period_days": o.period_days,
                        "tags": list(o.tags or ()),
                        "metadata": dict(o.metadata or {}),
                    }
                    for o in (self.offer_catalog.offers or ())
                ],
            },
            "pricing_model": {
                "id": getattr(self.pricing_model, "pricing_model_id", ""),
                "params": {},
            },
            "telemetry_schema": {
                "id": str(self.telemetry_schema.schema_id),
                "events": [
                    {
                        "event_type": ev.event_type,
                        "fields": [
                            {"name": f.name, "type": f.type, "required": bool(f.required)} for f in (ev.fields or ())
                        ],
                    }
                    for ev in (self.telemetry_schema.events or ())
                ],
            },
            "entitlements": {"keys": list(self.entitlements.keys or ())},
            "economics": {
                "target_cac_rub": int(self.economics.target_cac_rub),
                "target_payback_days": int(self.economics.target_payback_days),
                "min_ltv_cac_ratio": float(self.economics.min_ltv_cac_ratio),
            },
            "autopilot_contract_ref": str(self.autopilot_contract_ref or ""),
        }

    def items(self):
        return self.as_dict().items()

    def __iter__(self):
        return iter(self.as_dict().items())


class _DefaultPricingModel:
    pricing_model_id = "pricing_fixed@v1"

    def choose_offer_id(self, *, user_id: str, tenant_id: str, context: Mapping[str, Any]) -> str:
        return "basic"


__all__ = [
    "EntryPolicy",
    "Offer",
    "OfferCatalog",
    "PricingModel",
    "TelemetryField",
    "TelemetryEventSpec",
    "TelemetrySchema",
    "EntitlementsSpec",
    "ModuleSpec",
    "ModulesSpec",
    "ProductContract",
]
