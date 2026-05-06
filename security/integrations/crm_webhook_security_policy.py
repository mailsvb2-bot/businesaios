from __future__ import annotations

import hmac


class CrmWebhookSecurityPolicy:
    def validate(self, *, provided_signature: str, expected_signature: str) -> bool:
        if not provided_signature or not expected_signature:
            return False
        return hmac.compare_digest(str(provided_signature), str(expected_signature))
