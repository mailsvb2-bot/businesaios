from __future__ import annotations

# Canonical owner remains growth.seo.location_page_generator.
from growth.seo import LocationPageGenerator as GrowthLocationPageGenerator


class LocationPageGenerator:
    def __init__(self, *, generator: GrowthLocationPageGenerator | None = None) -> None:
        self._generator = generator or GrowthLocationPageGenerator()

    def build(self, city: str | dict[str, object]) -> dict[str, object]:
        payload = dict(city) if isinstance(city, dict) else {"city": str(city)}
        spec = self._generator.build(payload)
        city_name = str(payload.get("city") or "")
        return {
            "slug": f"/{city_name}/" if city_name else "/",
            "city": city_name,
            "spec": spec,
        }
