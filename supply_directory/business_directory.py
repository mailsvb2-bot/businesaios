from __future__ import annotations
from contracts.supply import BusinessSupplyProfile
from supply_directory.business_profile_store import BusinessProfileStore


class BusinessDirectory:
    def __init__(self, store: BusinessProfileStore | None = None) -> None:
        self._store = store or BusinessProfileStore()

    def add_profile(self, profile: BusinessSupplyProfile) -> None:
        self._store.add(profile)

    def list_profiles(self) -> tuple[BusinessSupplyProfile, ...]:
        return self._store.list_all()

    def get_profile(self, business_id: str) -> BusinessSupplyProfile | None:
        for profile in self._store.list_all():
            if profile.business_id == str(business_id):
                return profile
        return None

    def require_profile(self, business_id: str) -> BusinessSupplyProfile:
        profile = self.get_profile(business_id)
        if profile is None:
            raise KeyError(str(business_id))
        return profile

    def seed_defaults(self) -> None:
        if self._store.list_all():
            return
        self._store.add(BusinessSupplyProfile(
            business_id="biz-1", name="North Service", service_categories=("general", "local"), service_area_codes=("amsterdam",), price_band="mid", notification_channels=("email", "telegram"), tags=("verified",), active=True,
        ))
        self._store.add(BusinessSupplyProfile(
            business_id="biz-2", name="Premium Service", service_categories=("general", "premium"), service_area_codes=("amsterdam", "remote"), price_band="high", notification_channels=("email",), tags=("verified", "premium"), active=True,
        ))
        self._store.add(BusinessSupplyProfile(
            business_id="biz-3", name="Fast Service", service_categories=("general",), service_area_codes=("remote",), price_band="low", notification_channels=("sms",), tags=("new_supply",), active=True,
        ))
