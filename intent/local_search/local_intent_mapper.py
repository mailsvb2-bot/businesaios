from __future__ import annotations

from intent.local_search._signals import classify_local_intent


class LocalIntentMapper:
    def __call__(self, text: str) -> str:
        return classify_local_intent(text)
