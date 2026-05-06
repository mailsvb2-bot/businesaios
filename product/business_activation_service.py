from shared.kinded_payloads import build_kinded_payload
class BusinessActivationService:
    def activate(self, payload: dict) -> dict:
        return build_kinded_payload('activation_result', payload)
