from __future__ import annotations

class TimeWindowExtractor:
    def extract(self, event: dict[str, object]) -> str:
        return str(event.get("urgency_hint") or event.get("time_window") or "standard")
