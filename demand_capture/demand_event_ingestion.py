from __future__ import annotations

class DemandEventIngestion:
    def ingest(self, raw_event: dict[str, object]) -> dict[str, object]:
        if not isinstance(raw_event, dict):
            raise TypeError("raw_event must be dict")
        return dict(raw_event)
