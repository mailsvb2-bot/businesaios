from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.service_type_detector import ServiceTypeDetector


class IntentClassifier:
    def __init__(self) -> None:
        self._service_type = ServiceTypeDetector()

    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        return self._service_type.detect(signals, text)
