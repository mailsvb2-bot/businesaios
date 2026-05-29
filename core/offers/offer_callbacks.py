from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.observability.silent import swallow
from core.offers.offer_events import OFFER_ACCEPTED_V1, OFFER_DECLINED_V1


@dataclass(frozen=True)
class OfferCallback:
    kind: str  # "accept"|"decline"
    offer_id: str
    meta: dict[str, Any]


def parse_offer_callback(cb: str | None) -> OfferCallback | None:
    # format:
    #   offer:accept:<offer_id>
    #   offer:decline:<offer_id>
    # Backward-compatible extension:
    #   offer:accept:<offer_id>:<price_rub>
    #   offer:decline:<offer_id>:<price_rub>
    if not cb:
        return None
    s = str(cb)
    if not s.startswith("offer:"):
        return None
    parts = s.split(":")
    if len(parts) < 3:
        return None
    kind = parts[1].strip()
    offer_id = parts[2].strip()
    if kind not in ("accept", "decline"):
        return None
    if not offer_id:
        return None
    meta: dict[str, Any] = {}
    if len(parts) >= 4:
        pr = parts[3].strip()
        try:
            meta["price_rub"] = int(pr)
        except Exception:
            swallow(__name__, 'core/offers/offer_callbacks.py')
    return OfferCallback(kind=kind, offer_id=offer_id, meta=meta)


# ---------------------------------------------------------------------------
# Canonical outcome callback (typed, backward-compatible)
#
# Some patchsets expect a strict dataclass with price_rub as a field.
# We keep the existing OfferCallback + meta (used across current code),
# and provide a thin typed adapter to avoid "two parsers".
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OfferOutcomeCallback:
    kind: str  # "accept" | "decline"
    offer_id: str
    price_rub: int = 0


def parse_offer_outcome_callback(cb: str | None) -> OfferOutcomeCallback | None:
    parsed = parse_offer_callback(cb)
    if not parsed:
        return None
    price = 0
    try:
        price = int(parsed.meta.get("price_rub") or 0)
    except Exception:
        price = 0
    return OfferOutcomeCallback(kind=parsed.kind, offer_id=parsed.offer_id, price_rub=price)


def outcome_event_type(kind: str) -> str:
    return OFFER_ACCEPTED_V1 if str(kind) == "accept" else OFFER_DECLINED_V1
