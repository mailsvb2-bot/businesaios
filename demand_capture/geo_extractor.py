from __future__ import annotations


class GeoExtractor:
    def extract(self, event: dict[str, object]) -> str:
        return str(event.get("location_hint") or event.get("city") or event.get("geo") or "")
