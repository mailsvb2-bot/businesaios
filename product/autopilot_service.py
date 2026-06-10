from shared.kinded_payloads import build_kinded_payload


class AutopilotService:
    def run(self, payload: dict) -> dict:
        return build_kinded_payload('autopilot_result', payload)
