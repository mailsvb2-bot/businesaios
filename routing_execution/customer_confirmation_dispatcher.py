from __future__ import annotations

class CustomerConfirmationDispatcher:
    def confirm(self, *, request_id: str, business_id: str) -> dict[str, object]:
        return {"request_id": request_id, "business_id": business_id, "status": "customer_confirmation_sent"}
