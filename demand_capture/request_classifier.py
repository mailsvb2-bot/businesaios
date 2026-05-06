from __future__ import annotations

class RequestClassifier:
    def classify(self, text: str) -> str:
        lowered = str(text).lower()
        if "срочно" in lowered or "urgent" in lowered:
            return "urgent"
        if "цена" in lowered or "price" in lowered:
            return "price_check"
        return "standard"
