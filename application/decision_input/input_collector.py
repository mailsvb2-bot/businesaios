from __future__ import annotations

from application.decision_input.input_bundle import InputBundle


class InputCollector:
    def collect(self, business_id: str, profile: dict, signals: list[dict], constraints: dict) -> InputBundle:
        return InputBundle(business_id=business_id, profile=profile, signals=signals, constraints=constraints)
