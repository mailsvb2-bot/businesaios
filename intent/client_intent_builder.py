from __future__ import annotations

from contracts.demand import ClientIntent, ClientRequest
from intent.budget_sensitivity_detector import BudgetSensitivityDetector
from intent.high_value_intent_detector import HighValueIntentDetector
from intent.intent_confidence import compute_confidence
from intent.intent_explainer import IntentExplainer
from intent.intent_feature_builder import IntentFeatureBuilder
from intent.location_constraint_detector import LocationConstraintDetector
from intent.quality_preference_detector import QualityPreferenceDetector
from intent.repeat_purchase_detector import RepeatPurchaseDetector
from intent.service_type_detector import ServiceTypeDetector
from intent.trust_need_detector import TrustNeedDetector
from intent.urgency_detector import UrgencyDetector


class ClientIntentBuilder:
    def __init__(self) -> None:
        self._features = IntentFeatureBuilder()
        self._service = ServiceTypeDetector()
        self._urgency = UrgencyDetector()
        self._budget = BudgetSensitivityDetector()
        self._quality = QualityPreferenceDetector()
        self._location = LocationConstraintDetector()
        self._repeat = RepeatPurchaseDetector()
        self._high_value = HighValueIntentDetector()
        self._trust = TrustNeedDetector()
        self._explainer = IntentExplainer()

    def build(self, request: ClientRequest) -> ClientIntent:
        signals = self._features.build(request)
        labels = self._explainer.explain(signals)
        return ClientIntent(
            service_type=self._service.detect(signals, request.text),
            urgency=self._urgency.detect(signals, request.text),
            budget_band=self._budget.detect(signals, request.text),
            quality_band=self._quality.detect(signals, request.text),
            location_hint=request.location_hint or self._location.detect(signals, request.text),
            confidence=compute_confidence(signals),
            is_repeat_customer=self._repeat.detect(signals, request.text) == "true",
            needs_trust=self._trust.detect(signals, request.text) == "high",
            is_high_value=self._high_value.detect(signals, request.text) == "true",
            raw_labels=labels,
        )
