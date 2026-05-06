from __future__ import annotations

from typing import Any


def get_profile(directory: object, business_id: str) -> Any | None:
    target = str(business_id)
    getter = getattr(directory, 'get_profile', None)
    if callable(getter):
        return getter(target)
    lister = getattr(directory, 'list_profiles', None)
    if not callable(lister):
        return None
    for profile in lister():
        if getattr(profile, 'business_id', None) == target:
            return profile
    return None
