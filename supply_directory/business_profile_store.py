from __future__ import annotations

from contracts.supply import BusinessSupplyProfile


class BusinessProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[str, BusinessSupplyProfile] = {}

    def add(self, profile: BusinessSupplyProfile) -> None:
        business_id = str(profile.business_id)
        if business_id in self._profiles:
            raise ValueError(f"duplicate business profile: {business_id}")
        self._profiles[business_id] = profile

    def get(self, business_id: str) -> BusinessSupplyProfile:
        return self._profiles[str(business_id)]

    def list_all(self) -> tuple[BusinessSupplyProfile, ...]:
        return tuple(self._profiles.values())
