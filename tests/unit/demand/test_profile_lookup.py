from dataclasses import dataclass

from supply_directory.profile_lookup import get_profile


@dataclass(frozen=True)
class Profile:
    business_id: str


class Directory:
    def list_profiles(self):
        return (Profile('biz-1'), Profile('biz-2'))


def test_profile_lookup_falls_back_to_listing():
    assert get_profile(Directory(), 'biz-2').business_id == 'biz-2'
    assert get_profile(Directory(), 'biz-3') is None
