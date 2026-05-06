from __future__ import annotations

import pytest

from contracts.supply import BusinessSupplyProfile
from supply_directory.business_profile_store import BusinessProfileStore


def test_business_profile_store_rejects_duplicate_business_ids() -> None:
    store = BusinessProfileStore()
    profile = BusinessSupplyProfile(
        business_id='biz-1',
        name='A',
        service_categories=('general',),
        service_area_codes=('amsterdam',),
        price_band='mid',
        notification_channels=('email',),
        tags=(),
        active=True,
    )
    store.add(profile)
    with pytest.raises(ValueError, match='duplicate business profile: biz-1'):
        store.add(profile)
