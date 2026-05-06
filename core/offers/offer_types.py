from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class OfferEligibility:
    ok: bool
    reason: str = "ok"


@dataclass(frozen=True)
class OfferRender:
    offer_id: str
    variant: str
    price_rub: int
    text: str
    meta: Mapping[str, Any]


@dataclass(frozen=True)
class OfferSummary:
    offer_id: str
    title: str
    base_price_rub: int


@dataclass(frozen=True)
class OfferCatalog:
    """Canonical catalog interface (Engine-level)."""

    id: str

    def eligible(self, *, user_id: str, entitlements: Mapping[str, Any], context: Mapping[str, Any]) -> OfferEligibility:  # pragma: no cover
        raise NotImplementedError

    def render(
        self,
        *,
        offer_id: str,
        user_id: str,
        price_rub: int,
        variant: str,
        context: Mapping[str, Any],
    ) -> OfferRender:  # pragma: no cover
        raise NotImplementedError
