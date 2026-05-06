from __future__ import annotations

import hashlib
import hmac


def verify_hubspot_webhook_signature(*, client_secret: str, signature: str, method: str, uri: str, body: bytes, timestamp: str | None = None) -> bool:
    # Minimal helper for v3-style signed requests; callers may extend canonicalization as needed.
    payload = f"{method.upper()}{uri}".encode('utf-8') + body
    if timestamp:
        payload += timestamp.encode('utf-8')
    expected = hmac.new(client_secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
