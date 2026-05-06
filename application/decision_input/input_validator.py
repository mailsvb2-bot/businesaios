from __future__ import annotations
from application.decision_input.input_bundle import InputBundle


class InputValidator:
    REQUIRED_PROFILE_KEYS = {'goal', 'region'}

    def validate(self, bundle: InputBundle) -> tuple[bool, list[str]]:
        missing = sorted(self.REQUIRED_PROFILE_KEYS.difference(bundle.profile.keys()))
        if not bundle.business_id:
            missing.append('business_id')
        if missing:
            return False, [f'missing:{key}' for key in missing]
        return True, []
