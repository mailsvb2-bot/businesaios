from __future__ import annotations

from intent.local_search._signals import has_near_me_signal


class NearMeDetector:
    def __call__(self, text: str) -> bool:
        return has_near_me_signal(text)
