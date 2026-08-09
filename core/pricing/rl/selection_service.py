from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from core.offers.offer_types import OfferCatalog
from core.pricing.rl.guard import PricingSelectionContext
from core.pricing.rl.scoring import score_candidates
from core.scorers.pricing import choose_candidate as select_candidate

Json = dict[str, Any]
_KINDS = frozenset({"standard", "diagnostic", "audit", "implementation", "recurring"})


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _finite(value: object, name: str, *, unit: bool = False) -> float:
    _require(not isinstance(value, bool) and isinstance(value, int | float), f"{name} must be finite")
    result = float(value)
    _require(math.isfinite(result), f"{name} must be finite")
    if unit:
        _require(0 <= result <= 1, f"{name} must be between 0 and 1")
    return result


def _ids(values: Iterable[str] | None, name: str) -> set[str] | None:
    if values is None:
        return None
    _require(not isinstance(values, str | bytes | Mapping), f"{name} must be a collection of non-empty strings")
    items = list(values)
    _require(all(isinstance(item, str) and item.strip() for item in items), f"{name} must contain non-empty strings")
    normalized = [item.strip() for item in items]
    _require(len(normalized) == len(set(normalized)), f"{name} must not contain duplicates")
    return set(normalized)


def _commercial(offer: Any, index: int, seen: set[int]) -> tuple[str, int, bool, float, int]:
    meta = offer.meta.get("commercial", {}) if isinstance(offer.meta, Mapping) else {}
    _require(isinstance(meta, Mapping), f"commercial metadata must be a mapping for offer {offer.offer_id}")
    raw_kind, position, approval = meta.get("kind", "standard"), meta.get("position", index), meta.get("requires_human_approval", False)
    _require(isinstance(raw_kind, str) and bool(raw_kind.strip()), f"commercial.kind must be a non-empty string for offer {offer.offer_id}")
    kind = raw_kind.strip().lower()
    _require(kind in _KINDS, f"unsupported commercial kind for offer {offer.offer_id}")
    _require(not isinstance(position, bool) and isinstance(position, int) and position >= 0 and position not in seen, "commercial.position must be a unique non-negative integer")
    _require(isinstance(approval, bool), "commercial.requires_human_approval must be a boolean")
    price = offer.base_price_rub
    _require(not isinstance(price, bool) and isinstance(price, int) and price >= 0, "base_price_rub must be a non-negative integer")
    seen.add(position)
    return kind, position, approval, _finite(meta.get("min_evidence_score", 0.0), "commercial.min_evidence_score", unit=True), price


class PricingSelectionService:
    """Pure candidate ranking; never emits actions or mutates policy."""

    def choose_candidate(self, *, ctx: PricingSelectionContext, candidates: Iterable[Json], evidence: Json) -> Json:
        ctx.validate()
        scored = score_candidates(list(candidates), evidence=evidence)
        return {"tenant_id": ctx.tenant_id, "decision_id": ctx.decision_id, "correlation_id": ctx.correlation_id, "selected": select_candidate(scored), "scored_count": len(scored)}

    def select_from_catalog(self, *, ctx: PricingSelectionContext, catalog: OfferCatalog, evidence: Json, evidence_score: float,
                            candidate_offer_ids: Iterable[str] | None = None, completed_offer_ids: Iterable[str] = (), min_price_rub: int = 0,
                            max_price_rub: int | None = None) -> Json:
        score_gate = _finite(evidence_score, "evidence_score", unit=True)
        _require(not isinstance(min_price_rub, bool) and isinstance(min_price_rub, int) and min_price_rub >= 0, "min_price_rub must be a non-negative integer")
        _require(max_price_rub is None or (not isinstance(max_price_rub, bool) and isinstance(max_price_rub, int) and max_price_rub >= min_price_rub), "max_price_rub must be an integer >= min_price_rub")
        scores = evidence.get("candidate_scores")
        _require(isinstance(scores, Mapping), "candidate_scores evidence is required")
        requested, completed, offers = _ids(candidate_offer_ids, "candidate_offer_ids"), _ids(completed_offer_ids, "completed_offer_ids") or set(), list(catalog.list_offers())
        _require(requested is None or requested.issubset({str(offer.offer_id).strip() for offer in offers}), "candidate_offer_ids contain offers outside the canonical catalog")
        candidates: list[Json] = []
        seen: set[int] = set()
        for index, offer in enumerate(offers):
            if requested is not None and offer.offer_id not in requested:
                continue
            kind, position, approval, threshold, price = _commercial(offer, index, seen)
            if offer.offer_id in completed or score_gate < threshold or price < min_price_rub or (max_price_rub is not None and price > max_price_rub):
                continue
            _require(offer.offer_id in scores, f"candidate score missing for offer {offer.offer_id}")
            candidates.append({"offer_id": offer.offer_id, "title": offer.title, "price_rub": price, "score": _finite(scores[offer.offer_id], f"candidate score for {offer.offer_id}"), "commercial": {"kind": kind, "position": position, "requires_human_approval": approval}})
        _require(bool(candidates), "no eligible commercial offer candidates")
        return self.choose_candidate(ctx=ctx, candidates=candidates, evidence=evidence)

    select = choose_candidate
