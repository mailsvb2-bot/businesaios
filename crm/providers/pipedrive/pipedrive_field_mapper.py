from __future__ import annotations


class ProviderFieldMapper:
    def map_fields(self, payload: dict[str, object]) -> dict[str, object]:
        return dict(payload)
