from __future__ import annotations

# Canonical owner remains growth.seo.local_intent_mapper.
from growth.seo import LocalIntentMapper as GrowthLocalIntentMapper


class LocalIntentPageBuilder:
    def __init__(self, *, mapper: GrowthLocalIntentMapper | None = None) -> None:
        self._mapper = mapper or GrowthLocalIntentMapper()

    def build(self, city: str, category: str) -> dict[str, object]:
        payload = {"city": str(city), "category": str(category)}
        intent_map = self._mapper.map(payload)
        return {
            "slug": f"/{payload['city']}/{payload['category']}/",
            "city": payload["city"],
            "category": payload["category"],
            "intent_map": intent_map,
        }
