from __future__ import annotations

# Canonical owner remains growth.seo.service_page_generator.
from growth.seo import ServicePageGenerator as GrowthServicePageGenerator


class ServicePageGenerator:
    def __init__(self, *, generator: GrowthServicePageGenerator | None = None) -> None:
        self._generator = generator or GrowthServicePageGenerator()

    def build(self, category: str | dict[str, object]) -> dict[str, object]:
        payload = dict(category) if isinstance(category, dict) else {"category": str(category)}
        spec = self._generator.build(payload)
        category_name = str(payload.get("category") or "")
        return {
            "slug": f"/services/{category_name}/" if category_name else "/services/",
            "category": category_name,
            "spec": spec,
        }
