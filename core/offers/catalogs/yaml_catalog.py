from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from core.offers.models import OfferRule
from core.offers.offer_types import OfferCatalog, OfferEligibility, OfferRender


@dataclass(frozen=True)
class YamlOfferCatalogV1(OfferCatalog):
    """Offer catalog backed by a YAML spec (engine-level).

    Supports both legacy-YAML and v1-YAML shapes.

    Legacy shape (kept for backward compatibility):
      catalog_id: str
      schema_version: int
      offers:
        - offer_id: ...
          title: ...
          price_rub: int
          cooldown_days: int
          variants:
            a: {text: "..."}

    V1 shape (recommended):
      catalog_id: str
      offers:
        - offer_id: ...
          base_price_rub: int
          rules: {min_engagement: float, max_fatigue: float, cooldown_hours: int}
          variants:
            a: {title: "...", body: "..."}
          meta: { ... }
    """

    id: str
    schema_version: int
    _offers: Dict[str, Dict[str, Any]]

    @staticmethod
    def from_spec(spec: Mapping[str, Any]) -> "YamlOfferCatalogV1":
        cid = str(spec.get("catalog_id") or "").strip()
        sv = int(spec.get("schema_version") or 1)
        offers_raw = spec.get("offers") or []
        offers: Dict[str, Dict[str, Any]] = {}
        if isinstance(offers_raw, list):
            for it in offers_raw:
                if not isinstance(it, dict):
                    continue
                oid = str(it.get("offer_id") or "").strip()
                if not oid:
                    continue
                # Normalize known fields so render() can be deterministic.
                o: Dict[str, Any] = dict(it)

                # Rules (optional).
                rules_raw = o.get("rules") if isinstance(o.get("rules"), dict) else {}
                o["rules"] = {
                    "min_engagement": float(rules_raw.get("min_engagement") or 0.0),
                    "max_fatigue": float(rules_raw.get("max_fatigue") or 1.0),
                    "cooldown_hours": int(rules_raw.get("cooldown_hours") or 24),
                }

                # Price aliasing.
                if "base_price_rub" not in o and "price_rub" in o:
                    o["base_price_rub"] = o.get("price_rub")

                # Variants normalization.
                vraw = o.get("variants") if isinstance(o.get("variants"), dict) else {}
                vnorm: Dict[str, Dict[str, str]] = {}
                for vk, vv in vraw.items():
                    if not isinstance(vv, dict):
                        continue
                    # legacy: {text: "..."}
                    if "text" in vv and ("title" not in vv and "body" not in vv):
                        # Preserve exact legacy text rendering expectations.
                        vnorm[str(vk)] = {
                            "title": "",
                            "body": "",
                            "_legacy_text": str(vv.get("text") or ""),
                        }
                    else:
                        vnorm[str(vk)] = {
                            "title": str(vv.get("title") or ""),
                            "body": str(vv.get("body") or ""),
                        }
                if "a" not in vnorm:
                    vnorm["a"] = {"title": "", "body": ""}
                o["variants"] = vnorm

                # Meta normalization.
                o["meta"] = o.get("meta") if isinstance(o.get("meta"), dict) else {}

                offers[oid] = o
        return YamlOfferCatalogV1(id=cid, schema_version=sv, _offers=offers)

    def list_offers(self) -> list["OfferSummary"]:
        from core.offers.offer_types import OfferSummary

        out: list[OfferSummary] = []
        for oid in sorted(self._offers.keys()):
            off = self._offers.get(oid) or {}
            title = str(off.get("title") or oid)
            bpr = int(off.get("base_price_rub") or off.get("price_rub") or 0)
            out.append(OfferSummary(offer_id=str(oid), title=title, base_price_rub=bpr))
        return out

    def eligible(self, *, user_id: str, entitlements: Mapping[str, Any], context: Mapping[str, Any]) -> OfferEligibility:
        # YAML catalogs are content-only; eligibility is handled upstream (DecisionCore).
        return OfferEligibility(ok=True, reason="ok")

    def render(self, *, offer_id: str, user_id: str, price_rub: int, variant: str, context: Mapping[str, Any]) -> OfferRender:
        oid = str(offer_id or "").strip()
        off = self._offers.get(oid) or {}

        # Variants.
        variants = off.get("variants") if isinstance(off.get("variants"), dict) else {}
        vkey = str(variant or "").strip() or "a"
        v = variants.get(vkey) or variants.get("a") or {}
        title = str(off.get("title") or oid)

        # Prefer v1 title/body; legacy "text" is already mapped into body by from_spec().
        if isinstance(v, dict) and "_legacy_text" in v:
            # Strict backwards compatibility: return the legacy variant text as-is.
            text = str(v.get("_legacy_text") or "")
        else:
            v_title = str(v.get("title") or "").strip() if isinstance(v, dict) else ""
            v_body = str(v.get("body") or "").strip() if isinstance(v, dict) else ""

            if v_title or v_body:
                # Canonical formatting; products own copy in YAML.
                chunks = []
                if v_title:
                    chunks.append(v_title)
                if v_body:
                    chunks.append(v_body)
                chunks.append(f"Цена: {int(price_rub)} ₽")
                text = "\n\n".join(chunks)
            else:
                # Stable fallback, never crash.
                text = f"💡 Предложение: {title} за {int(price_rub)} ₽"

        # Rules/meta are best-effort hints for upstream logic.
        rules_raw = off.get("rules") if isinstance(off.get("rules"), dict) else {}
        rule = OfferRule(
            min_engagement=float(rules_raw.get("min_engagement") or 0.0),
            max_fatigue=float(rules_raw.get("max_fatigue") or 1.0),
            cooldown_hours=int(rules_raw.get("cooldown_hours") or 24),
        )
        meta = dict(off.get("meta") or {}) if isinstance(off.get("meta"), dict) else {}
        meta.update(
            {
                "catalog": self.id,
                "schema_version": int(self.schema_version),
                "title": title,
                "rules": {
                    "min_engagement": rule.min_engagement,
                    "max_fatigue": rule.max_fatigue,
                    "cooldown_hours": rule.cooldown_hours,
                },
            }
        )
        return OfferRender(
            offer_id=oid,
            variant=str(vkey),
            price_rub=int(price_rub),
            text=text,
            meta=meta,
        )