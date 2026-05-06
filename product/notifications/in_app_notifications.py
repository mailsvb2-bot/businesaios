from shared.kinded_payloads import build_kinded_payload
class InAppNotifications:
    def send(self, payload: dict) -> dict:
        return build_kinded_payload('notification', payload)
