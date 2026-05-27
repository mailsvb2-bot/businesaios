from __future__ import annotations

from application.decision_input.input_bundle import InputBundle


class InputNormalizer:
    def normalize(self, bundle: InputBundle) -> InputBundle:
        normalized_signals = [dict(sorted(signal.items())) for signal in bundle.signals]
        return InputBundle(
            business_id=bundle.business_id,
            objective=bundle.objective,
            profile=dict(sorted(bundle.profile.items())),
            signals=normalized_signals,
            constraints=dict(sorted(bundle.constraints.items())),
        )
