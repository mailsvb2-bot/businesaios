from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from core.offers.offer_types import OfferCatalog
from core.pricing.rl.guard import PricingSelectionContext
from core.pricing.rl.scoring import score_candidates
from core.scorers.pricing import choose_candidate as select_candidate

Json = dict[str, Any]
_ALLOWED_COMMERCIAL_KINDS = frozenset({"standard", "diagnostic", "audit", "implementation", "recurring"})


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _unit_interval(value: object, name: str) -> float:
    result = _finite(value, name)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return result


def _strict_ids(values: Iterable[str] | None, name: str) -> set[str] | None:
    if values is None:
        return None
    if isinstance(values, str | bytes | Mapping):
        raise ValueError(f"{name} must be a collection of non-empty strings")
    items = list(values)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{name} must contain non-empty strings")
    normalized = [item.strip() for item in items]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    return set(normalized)


class PricingSelectionService:
    """Pure candidate ranking; never emits actions or mutates policy."""

    def choose_candidate(self, *, ctx: PricingSelectionContext, candidates: Iterable[Json], evidence: Json) -> Json:
        ctx.validate()
        scored = score_candidates(list(candidates), evidence=evidence)
        return {"tenant_id": ctx.tenant_id, "decision_id": ctx.decision_id, "correlation_id": ctx.correlation_id,
                "selected": select_candidate(scored), "scored_count": len(scored)}

    def select_from_catalog(
        self,
        *,
        ctx: PricingSelectionContext,
        catalog: OfferCatalog,
        evidence: Json,
        evidence_score: float,
        candidate_offer_ids: Iterable[str] | None = None,
        completed_offer_ids: Iterable[str] = (),
        min_price_rub: int = 0,
        max_price_rub: int | None = None,
    ) -> Json:
        """Constrain the one canonical offer catalog, then use the existing selector."""
        score_gate = _unit_interval(evidence_score, "evidence_score")
        if isinstance(min_price_rub, bool) or not isinstance(min_price_rub, int) or min_price_rub < 0:
            raise ValueError("min_price_rub must be a non-negative integer")
        if max_price_rub is not None and (isinstance(max_price_rub, bool) or not isinstance(max_price_rub, int) or max_price_rub < min_price_rub):
            raise ValueError("max_price_rub must be an integer >= min_price_rub")
        raw_scores = evidence.get("candidate_scores")
        if not isinstance(raw_scores, Mapping):
            raise ValueError("candidate_scores evidence is required")
        requested = _strict_ids(candidate_offer_ids, "candidate_offer_ids")
        completed = _strict_ids(completed_offer_ids, "completed_offer_ids") or set()
        offers = list(catalog.list_offers())
        catalog_ids = {str(offer.offer_id).strip() for offer in offers}
        if requested is not None and not requested.issubset(catalog_ids):
            raise ValueError("candidate_offer_ids contain offers outside the canonical catalog")
        candidates: list[Json] = []
        seen_positions: set[int] = set()
        for index, offer in enumerate(offers):
            if requested is not None and offer.offer_id not in requested:
                continue
            commercial = offer.meta.get("commercial", {}) if isinstance(offer.meta, Mapping) else {}
            if not isinstance(commercial, Mapping):
                raise ValueError(f"commercial metadata must be a mapping for offer {offer.offer_id}")
            position = commercial.get("position", index)
            approval = commercial.get("requires_human_approval", False)
            raw_kind = commercial.get("kind", "standard")
            if not isinstance(raw_kind, str) or not raw_kind.strip():
                raise ValueError(f"commercial.kind must be a non-empty string for offer {offer.offer_id}")
            kind = raw_kind.strip().lower()
            if kind not in _ALLOWED_COMMERCIAL_KINDS:
                raise ValueError(f"unsupported commercial kind for offer {offer.offer_id}")
            if isinstance(position, bool) or not isinstance(position, int) or position < 0 or position in seen_positions:
                raise ValueError("commercial.position must be a unique non-negative integer")
            if not isinstance(approval, bool):
                raise ValueError("commercial.requires_human_approval must be a boolean")
            seen_positions.add(position)
            threshold = _unit_interval(commercial.get("min_evidence_score", 0.0), "commercial.min_evidence_score")
            price = offer.base_price_rub
            if isinstance(price, bool) or not isinstance(price, int) or price < 0:
                raise ValueError("base_price_rub must be a non-negative integer")
            if offer.offer_id in completed or score_gate < threshold or price < min_price_rub or (max_price_rub is not None and price > max_price_rub):
                continue
            if offer.offer_id not in raw_scores:
                raise ValueError(f"candidate score missing for offer {offer.offer_id}")
            score = _finite(raw_scores[offer.offer_id], f"candidate score for {offer.offer_id}")
            candidates.append({"offer_id": offer.offer_id, "title": offer.title, "price_rub": price, "score": score,
                               "commercial": {"kind": kind, "position": position, "requires_human_approval": approval}})
        if not candidates:
            raise ValueError("no eligible commercial offer candidates")
        return self.choose_candidate(ctx=ctx, candidates=candidates, evidence=evidence)

    select = choose_candidate
