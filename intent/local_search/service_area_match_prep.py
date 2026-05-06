from __future__ import annotations

from intent.local_search._signals import build_service_area_match_prep


class ServiceAreaMatchPrep:
    def __call__(self, text: str) -> dict[str, object]:
        return build_service_area_match_prep(text)
