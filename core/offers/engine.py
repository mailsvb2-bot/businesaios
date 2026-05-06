from __future__ import annotations

"""Offer Engine (shared service).

Contract:
  - Input: WorldState (tenant-scoped), product contract, behavioral_state
  - Output: selected offer + chosen variant + price
  - Side-effects: none (policy/executor emit events separately)

This module is intentionally conservative: it can run in "best-effort" mode and
fallback to legacy offer catalog if needed.
"""

"""Canonical Offers Engine.

P0 invariant: there must be exactly one implementation of the offers engine.

Historically the repo had two parallel implementations:
  - core/offers/offer_engine.py (runtime used)
  - core/offers/engine.py (tests used)

This module is the single source of truth now.

It contains:
  - OfferEngine (catalog resolution + rendering + cooldown/eligibility checks)
  - decide_offer() helpers used by CAC-aware tests

legacy import path ``core.offers.offer_engine`` is now served from ``core.offers`` package aliases.
"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from core.offers.catalog_registry import OfferCatalogRegistry, default_offer_catalog_registry
from core.offers.models import OfferSpec, OfferVariant
from core.offers.offer_keyboards import offer_outcome_kb
from core.offers.offer_types import OfferRender
from core.marketing.variants import choose_variant as choose_marketing_variant
from core.observability.silent import swallow
from core.offers.catalog_resolution import resolve_catalog
from core.offers.offer_catalog_resolver import OfferCatalogResolver
from core.offers.selection_policy import clamp_band as _clamp_band, choose_band as _choose_band, choose_offer_variant, choose_slot as _choose_slot, eligible
from core.offers.cooldown_policy import allow_offer_by_cooldown
from core.offers.eligibility import check_offer_eligibility


def decide_offer(
    *,
    offer: OfferSpec,
    user_id: str,
    tenant_id: str,
    behavior: Mapping[str, Any],
    max_band: str | None = None,
) -> OfferDecision:
    """Decide offer variant and band from behavior (CAC-aware tests and callers)."""
    if not offer.variants:
        raise ValueError("offer must have at least one variant")
    band = _choose_band(behavior=behavior or {})
    band = _clamp_band(band=band, max_band=max_band)
    variant = choose_offer_variant(seed=str(user_id or "1"), variants=list(offer.variants))
    return OfferDecision(
        offer_id=str(offer.offer_id),
        variant_key=str(variant.key),
        price_rub=int(offer.base_price_rub or 0),
        text=str(variant.body or variant.title or ""),
        slot="default_menu",
        band=band,
    )


@dataclass(frozen=True)
class OfferDecision:
    offer_id: str
    variant_key: str
    price_rub: int
    text: str
    # Deterministic UX placement + price band (pre-ML, explainable)
    slot: str = "default_menu"
    band: str = "standard"




@dataclass
class OfferEngine:
    """Engine-level offer helper.

    - Resolves offer catalogs (tenant/product/env + optional YAML override)
    - Chooses A/B variant per UX step
    - Renders text + attaches canonical outcome keyboard

    DecisionCore remains sovereign: it chooses WHICH offer_id to attempt.
    OfferEngine only applies *mechanical* constraints and rendering.
    """

    catalogs: OfferCatalogRegistry

    @classmethod
    def default(cls) -> "OfferEngine":
        return OfferEngine(catalogs=default_offer_catalog_registry())

    def render_offer(
        self,
        *,
        product: Mapping[str, Any],
        tenant_id: str | None = None,
        user_id: str,
        offer_id: str,
        price_rub: int,
        step_key: str,
        seed: str = "1",
        bandit: Dict[str, Dict[str, float]] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> OfferRender:
        prod = dict(product or {})
        catalog = resolve_catalog(
            catalogs=self.catalogs,
            product=prod,
            tenant_id=tenant_id,
            context=context,
        )

        variant = choose_marketing_variant(user_id=str(user_id), step_key=str(step_key), seed=str(seed), bandit=bandit)
        ctx = dict(context or {})
        rendered = catalog.render(
            offer_id=str(offer_id),
            user_id=str(user_id),
            price_rub=int(price_rub),
            variant=str(variant),
            context=ctx,
        )

        # Canonical: UI bundle for offer outcome lives in meta.
        try:
            meta2 = dict(rendered.meta or {})
            meta2.setdefault("reply_markup", offer_outcome_kb(str(offer_id), price_rub=int(rendered.price_rub)))
            rendered = OfferRender(
                offer_id=str(rendered.offer_id),
                variant=str(rendered.variant),
                price_rub=int(rendered.price_rub),
                text=str(rendered.text),
                meta=meta2,
            )
        except (TypeError, ValueError, KeyError) as e:
            from core.observability.throttled_logger import exception_throttled
            import logging
            exception_throttled(logging.getLogger(__name__), key="offers.engine.render_offer", msg=f"{type(e).__name__}")
        return rendered

    def should_show_offer(
        self,
        *,
        now_ms: int,
        product: Mapping[str, Any],
        tenant_id: str,
        user_id: str,
        entitlements: Mapping[str, Any],
        payment_status: str | None,
        offer_id: str,
        cooldown_store=None,
    ) -> tuple[bool, dict]:
        elig = check_offer_eligibility(
            product=product,
            tenant_id=tenant_id,
            entitlements=entitlements,
            payment_status=payment_status,
            offer_id=offer_id,
        )
        if not elig.eligible:
            return False, {"reason": elig.reason}

        cd_days = 0
        last_shown = None
        try:
            prod = dict(product or {})
            resolver = OfferCatalogResolver(catalogs=self.catalogs)
            cat = resolver.resolve_from_product(
                product=prod,
                tenant_id=tenant_id,
                context={"tenant_id": tenant_id, "environment": prod.get("environment")},
            )
            raw = getattr(cat, "_offers", None)
            if isinstance(raw, dict):
                off = raw.get(str(offer_id)) or {}
                if "cooldown_days" in off:
                    cd_days = int(off.get("cooldown_days") or 0)
                else:
                    rules = off.get("rules") if isinstance(off.get("rules"), dict) else {}
                    ch = int(rules.get("cooldown_hours") or 0)
                    cd_days = int((ch + 23) // 24) if ch > 0 else 0
        except Exception:
            cd_days = 0

        try:
            if cooldown_store is not None and hasattr(cooldown_store, "get_last_shown_ms"):
                last_shown = cooldown_store.get_last_shown_ms(
                    tenant_id=str(tenant_id),
                    user_id=str(user_id),
                    offer_id=str(offer_id),
                )
        except Exception:
            last_shown = None

        cd = allow_offer_by_cooldown(now_ms=int(now_ms), last_shown_ms=last_shown, cooldown_days=int(cd_days))
        if not cd.allowed:
            return False, {"reason": cd.reason, "last_shown_ms": cd.last_shown_ms, "cooldown_days": cd_days}
        return True, {"reason": "ok", "cooldown_days": cd_days, "last_shown_ms": cd.last_shown_ms}