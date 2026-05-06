from __future__ import annotations

class ContactExtractor:
    def extract(self, event: dict[str, object]) -> str:
        return str(event.get("phone") or event.get("email") or event.get("contact") or "")
