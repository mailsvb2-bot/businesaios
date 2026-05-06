from __future__ import annotations

class SessionLinker:
    def link(self, event: dict[str, object]) -> str:
        customer_id = str(event.get("customer_id") or event.get("contact_id") or "anon")
        return str(event.get("session_id") or f"session:{customer_id}")
