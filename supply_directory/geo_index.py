from __future__ import annotations
from contracts.supply import BusinessSupplyProfile

class GeoIndex:
    def lookup(self, profiles: tuple[BusinessSupplyProfile, ...], query: str) -> tuple[BusinessSupplyProfile, ...]:
        result = []
        q = str(query).lower()
        for profile in profiles:
            value = getattr(profile, "service_area_codes")
            if isinstance(value, tuple) and any(q in str(v).lower() for v in value):
                result.append(profile)
            elif q in str(value).lower():
                result.append(profile)
        return tuple(result)
