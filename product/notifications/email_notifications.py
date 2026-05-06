from shared.kinded_payloads import build_kinded_payload
class EmailNotifications:
    def send(self, payload: dict) -> dict:
        return build_kinded_payload('notification', payload)
