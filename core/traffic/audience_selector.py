from __future__ import annotations

"""Audience interest selector.

AudienceSelector — pure, sync, keyword-heuristic (domain default, no I/O).
Can be upgraded at wiring time by merging LLM-generated interests from
LLMCreativeGenerator.generate_async() into the audience spec.

The LLM interests are injected via TrafficStrategyService.plan_7d() when
the creative generator returns them alongside the creative.
"""

from dataclasses import dataclass



@dataclass(frozen=True)
class AudienceSelector:
    """Keyword-heuristic interest suggester (pure, deterministic, no I/O).

    Returns coarse interest tags compatible with platform ad targeting.
    Production targeting is enriched by LLMCreativeGenerator interests
    which are merged in TrafficStrategyService.plan_7d().
    """

    def suggest_interests(self, *, what: str) -> list[str]:
        """Return a list of English interest tags for a given product/service description."""
        w = (what or "").lower()
        tags: list[str] = []

        # Healthcare / dental
        if any(k in w for k in ("стомат", "dent", "зуб", "клиник", "медиц", "врач", "health")):
            tags += ["healthcare", "dentistry"]
        # Fitness / wellness
        if any(k in w for k in ("фитнес", "спорт", "зал", "трениров", "йога", "fitness", "gym")):
            tags += ["fitness", "sports"]
        # Beauty
        if any(k in w for k in ("красот", "косметик", "маникюр", "салон", "beauty", "nail")):
            tags += ["beauty", "personal_care"]
        # Home / repair
        if any(k in w for k in ("ремонт", "стро", "отделк", "home", "repair", "interior")):
            tags += ["home_improvement", "construction"]
        # Education
        if any(k in w for k in ("обучен", "курс", "школ", "урок", "educ", "tutor")):
            tags += ["education", "online_courses"]
        # Food / restaurant
        if any(k in w for k in ("еда", "ресторан", "кафе", "доставк", "пицц", "food", "delivery")):
            tags += ["food_delivery", "restaurants"]
        # Legal / finance
        if any(k in w for k in ("юрид", "адвок", "бухгалт", "налог", "legal", "finance")):
            tags += ["legal_services", "finance"]
        # Real estate
        if any(k in w for k in ("недвиж", "аренд", "квартир", "real_estate", "rent")):
            tags += ["real_estate"]
        # Auto
        if any(k in w for k in ("авто", "машин", "сто ", "детейл", "auto", "car")):
            tags += ["automotive", "car_repair"]

        # Deduplicate, preserve order
        seen: set[str] = set()
        result: list[str] = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def merge_llm_interests(
        self, heuristic: list[str], llm: list[str]
    ) -> list[str]:
        """Merge heuristic + LLM interests, deduplicated, LLM-first."""
        seen: set[str] = set()
        merged: list[str] = []
        for t in list(llm) + list(heuristic):
            t = str(t).strip().lower()
            if t and t not in seen:
                seen.add(t)
                merged.append(t)
        return merged[:8]
