from __future__ import annotations

class BusinessNotificationDispatcher:
    def notify(self, *, business_id: str, channel: str) -> dict[str, object]:
        return {"business_id": business_id, "channel": channel, "status": "notified"}
