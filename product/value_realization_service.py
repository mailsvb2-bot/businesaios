from shared.kinded_payloads import build_kinded_payload


class ValueRealizationService:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload('value_realization', payload)
