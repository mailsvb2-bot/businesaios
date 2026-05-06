from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Mapping


CANON_AUDIT_EXPORT_VERIFIER = True


class AuditExportVerifier:
    """Verifies signed external audit export payloads."""

    def __init__(self, shared_secret: str) -> None:
        self._secret = str(shared_secret).encode('utf-8')

    def verify(self, *, payload: Mapping[str, Any], signature: str) -> bool:
        canonical = json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        )
        expected = hmac.new(self._secret, canonical.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, str(signature).strip())


__all__ = [
    'CANON_AUDIT_EXPORT_VERIFIER',
    'AuditExportVerifier',
]
