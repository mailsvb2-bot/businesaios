from __future__ import annotations

from intent.local_search._signals import build_local_service_query


class LocalServiceQueryParser:
    def __call__(self, text: str) -> dict[str, object]:
        return build_local_service_query(text)
