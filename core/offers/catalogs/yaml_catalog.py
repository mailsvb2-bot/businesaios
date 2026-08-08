from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.offers.offer_types import OfferCatalog, OfferEligibility, OfferRender, OfferSummary


@dataclass(frozen=True)
class YamlOfferCatalogV1(OfferCatalog):
    """YAML-backed catalog supporting legacy and v1 offer shapes."""

    id: str
    schema_version: int
    _offers: dict[str, dict[str, Any]]

    @staticmethod
    def from_spec(spec: Mapping[str, Any]) -> YamlOfferCatalogV1:
        cid = str(spec.get("catalog_id") or "").strip()
        sv = int(spec.get("schema_version") or 1)
        offers: dict[str, dict[str, Any]] = {}
        for item in spec.get("offers") or []:
            if not isinstance(item, dict):
                continue
            oid = str(item.get("offer_id") or "").strip()
            if not oid:
                continue
            offer: dict[str, Any] = dict(item)
            raw_rules = offer.get("rules") if isinstance(offer.get("rules"), dict) else {}
            offer["rules"] = {
                "min_engagement": float(raw_rules.get("min_engagement") or 0.0),
                "max_fatigue": float(raw_rules.get("max_fatigue") or 1.0),
                "cooldown_hours": int(raw_rules.get("cooldown_hours") or 24),
            }
            if "base_price_rub" not in offer and "price_rub" in offer:
                offer["base_price_rub"] = offer.get("price_rub")
            variants: dict[str, dict[str, str]] = {}
            raw_variants = offer.get("variants") if isinstance(offer.get("variants"), dict) else {}
            for key, value in raw_variants.items():
                if not isinstance(value, dict):
                    continue
                if "text" in value and "title" not in value and "body" not in value:
                    variants[str(key)] = {"title": "", "body": "", "_legacy_text": str(value.get("text") or "")}
                else:
                    variants[str(key)] = {"title": str(value.get("title") or ""), "body": str(value.get("body") or "")}
            variants.setdefault("a", {"title": "", "body": ""})
            offer["variants"] = variants
            offer["meta"] = offer.get("meta") if isinstance(offer.get("meta"), dict) else {}
            offers[oid] = offer
        return YamlOfferCatalogV1(id=cid, schema_version=sv, _offers=offers)

    def list_offers(self) -> list[OfferSummary]:
        out: list[OfferSummary] = []
        for oid in sorted(self._offers):
            offer = self._offers.get(oid) or {}
            raw_price = offer["base_price_rub"] if "base_price_rub" in offer else offer.get("price_rub", 0)
            if isinstance(raw_price, bool) or not isinstance(raw_price, int) or raw_price < 0:
                raise ValueError(f"base_price_rub must be a non-negative integer for offer {oid}")
            out.append(OfferSummary(offer_id=oid, title=str(offer.get("title") or oid),
                base_price_rub=raw_price, meta=dict(offer.get("meta") or {})))
        return out

    def eligible(self, *, user_id: str, entitlements: Mapping[str, Any], context: Mapping[str, Any]) -> OfferEligibility:
        return OfferEligibility(ok=True, reason="ok")

    def render(self, *, offer_id: str, user_id: str, price_rub: int, variant: str, context: Mapping[str, Any]) -> OfferRender:
        oid = str(offer_id or "").strip()
        offer = self._offers.get(oid) or {}
        variants = offer.get("variants") if isinstance(offer.get("variants"), dict) else {}
        vkey = str(variant or "").strip() or "a"
        selected = variants.get(vkey) or variants.get("a") or {}
        title = str(offer.get("title") or oid)
        if isinstance(selected, dict) and "_legacy_text" in selected:
            text = str(selected.get("_legacy_text") or "")
        else:
            v_title = str(selected.get("title") or "").strip() if isinstance(selected, dict) else ""
            v_body = str(selected.get("body") or "").strip() if isinstance(selected, dict) else ""
            text = "\n".join(part for part in (v_title or title, v_body) if part)
        return OfferRender(offer_id=oid, variant=vkey, price_rub=int(price_rub), text=text,
                           meta={"catalog": self.id, "title": title, "schema_version": self.schema_version})
