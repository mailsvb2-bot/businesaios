from shared.kinded_payloads import build_kinded_payload


class CustomerAcquisitionService:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload('customer_acquisition_plan', payload)
