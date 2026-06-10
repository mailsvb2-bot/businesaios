from __future__ import annotations


class CalendarStateFeed:
    def fetch(self, business_id: str) -> dict[str, object]:
        return {'_source': 'calendar', 'available_slots': 3, 'queue_load': 0.2} | {"business_id": str(business_id)}
