from shared.kinded_payloads import build_kinded_payload


class OnboardingCopy:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload('copy', payload)
