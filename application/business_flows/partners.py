"""Partner search: owner-curated candidates ranked against an audience goal.

Ported from clientplatform ``partner_scoring`` (explainable 0..100 score).
Advisory only: nothing here contacts a partner; first contact needs a lawful
basis (opted-in or existing relationship), public contacts only prepare a proposal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from application.business_flows.projection import stable_id

CONTACTABILITY = {"opted_in": 100.0, "existing": 95.0, "public": 82.0, "unknown": 20.0, "none": 0.0}
FIRST_CONTACT_OK = frozenset({"opted_in", "existing"})


@dataclass(frozen=True)
class Partner:
    partner_id: str
    name: str
    tags: tuple[str, ...]
    followers: int | None
    basis: str
    contact: str
    competitor: bool = False


@dataclass(frozen=True)
class Fit:
    partner: Partner
    total: float
    reasons: tuple[str, ...]


def parse_partner(arg: str) -> dict[str, Any]:
    """``Имя | теги, через, запятую | подписчики | opted_in|existing|public|unknown | контакт [| competitor]``."""
    parts = [p.strip() for p in str(arg or "").split("|")]
    if len(parts) < 4 or not parts[0]:
        raise ValueError("partner_format: /partner_add Имя | теги | подписчики | основание | контакт")
    basis = parts[3].casefold()
    if basis not in CONTACTABILITY:
        raise ValueError("partner_contact_basis_invalid")
    followers = int(parts[2]) if parts[2].isdigit() else None
    return {
        "step": "partner_added",
        "partner_id": stable_id("partner", parts[0].casefold()),
        "name": parts[0][:120],
        "tags": [t.strip()[:40] for t in parts[1].split(",") if t.strip()][:12],
        "followers": followers,
        "basis": basis,
        "contact": (parts[4] if len(parts) > 4 else "")[:200],
        "competitor": len(parts) > 5 and parts[5].casefold() == "competitor",
    }


def replay(payloads: list[dict[str, Any]]) -> dict[str, Partner]:
    out: dict[str, Partner] = {}
    for p in payloads:
        if p.get("step") == "partner_added":
            out[str(p["partner_id"])] = Partner(
                str(p["partner_id"]),
                str(p["name"]),
                tuple(p.get("tags") or ()),
                p.get("followers"),
                str(p["basis"]),
                str(p.get("contact") or ""),
                bool(p.get("competitor")),
            )
        elif p.get("step") == "partner_removed":
            out.pop(str(p.get("partner_id")), None)
    return out


def score(partner: Partner, goal_terms: list[str]) -> Fit:
    goal = {_norm(t) for t in goal_terms if _norm(t)}
    cand = {_norm(t) for t in (*partner.tags, partner.name) if _norm(t)}
    overlap = sum(1 for g in goal if any(g in c or c in g for c in cand)) / max(1, len(goal)) if goal and cand else 0.0
    relevance = min(100.0, 28.0 + overlap * 72.0) if goal else 55.0
    contactability = CONTACTABILITY[partner.basis] if partner.contact else min(CONTACTABILITY[partner.basis], 10.0)
    reasons, penalty = [], 0.0
    if partner.competitor:
        penalty += 65.0
        reasons.append("прямой конкурент")
    if partner.basis not in FIRST_CONTACT_OK:
        penalty += 20.0
        reasons.append("нет основания для первого контакта — только подготовить предложение")
    if partner.followers is not None and partner.followers > 1_000_000:
        penalty += 8.0
        reasons.append("очень большая аудитория — ниже вероятность ответа")
    if overlap > 0.35:
        reasons.append("сильное пересечение аудитории")
    total = relevance * 0.4 + _audience(partner.followers) * 0.2 + contactability * 0.2 + 50.0 * 0.2 - penalty
    return Fit(partner, max(0.0, min(100.0, total)), tuple(reasons))


def rank(partners: dict[str, Partner], goal_terms: list[str], *, limit: int = 10) -> list[Fit]:
    fits = [score(p, goal_terms) for p in partners.values()]
    return sorted(fits, key=lambda f: (-f.total, f.partner.name))[:limit]


def _audience(followers: int | None) -> float:
    if followers is None:
        return 55.0
    if followers <= 0:
        return 20.0
    return max(30.0, min(100.0, 100.0 - abs(math.log10(followers) - math.log10(8_000)) * 28.0))


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


__all__ = ["Fit", "Partner", "parse_partner", "rank", "replay", "score"]
