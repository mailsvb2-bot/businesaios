from shared.kinded_payloads import build_kinded_payload


class GrowthVisibilityService:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload('growth_visibility', payload)
