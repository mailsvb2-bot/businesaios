from __future__ import annotations

from supply_directory.business_directory import BusinessDirectory


def test_business_directory_can_fetch_profile_by_id() -> None:
    directory = BusinessDirectory()
    directory.seed_defaults()
    profile = directory.get_profile('biz-2')
    assert profile is not None
    assert profile.business_id == 'biz-2'
