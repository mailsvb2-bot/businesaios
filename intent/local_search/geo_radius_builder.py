from __future__ import annotations

from intent.local_search._signals import build_geo_radius


class GeoRadiusBuilder:
    def __call__(self, text: str) -> int:
        return build_geo_radius(text)
