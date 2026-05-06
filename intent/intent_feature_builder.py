from __future__ import annotations
from contracts.demand import ClientIntentSignal
from contracts.demand import ClientRequest

class IntentFeatureBuilder:
    def build(self, request: ClientRequest) -> tuple[ClientIntentSignal, ...]:
        text = request.text.lower()
        signals: list[ClientIntentSignal] = []
        if "срочно" in text or "urgent" in text:
            signals.append(ClientIntentSignal("urgency", "high", 0.9, request.channel))
        if "дорого" in text or "цена" in text or "price" in text:
            signals.append(ClientIntentSignal("budget", "sensitive", 0.7, request.channel))
        if "рядом" in text or "near me" in text:
            signals.append(ClientIntentSignal("location", "local", 0.9, request.channel))
        if "отзывы" in text or "review" in text:
            signals.append(ClientIntentSignal("trust", "high", 0.8, request.channel))
        return tuple(signals)
