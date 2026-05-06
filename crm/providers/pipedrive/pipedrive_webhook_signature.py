from __future__ import annotations

import hashlib
import hmac


def verify_pipedrive_webhook_signature(*, client_secret: str, signature: str, body: bytes) -> bool:
    expected = hmac.new(client_secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
