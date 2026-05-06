from shared.kinded_payloads import build_kinded_payload
class FirstLeadDetector:
    def detect(self, payload: dict) -> dict:
        return build_kinded_payload('magic_moment', payload)
