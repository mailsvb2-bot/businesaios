from __future__ import annotations


class OriginTracker:
    def track(self, event: dict[str, object]) -> str:
        return str(event.get("origin") or event.get("channel") or "unknown")
