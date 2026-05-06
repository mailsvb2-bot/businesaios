from __future__ import annotations

"""Decision signing primitives.

Law:
  - DecisionCore is the ONLY issuer of DecisionEnvelope.
  - RuntimeGuard is the ONLY verifier of irreversible actions.
  - Signatures MUST be stable over canonical JSON bytes of the signed payload.

This module provides a small wrapper so DecisionCore does not hand-roll crypto.
"""

import base64
import hashlib
import hmac
from typing import Any, Dict, Tuple

from core.utils.canonical import canonical_json_bytes

class DecisionSigner:
    @staticmethod
    def sign(*, payload: Dict[str, Any], secret: bytes) -> str:
        mac = hmac.new(secret, canonical_json_bytes(payload), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(mac).decode("ascii")

    @staticmethod
    def verify(*, payload: Dict[str, Any], signature: str, secret: bytes) -> bool:
        try:
            expected = DecisionSigner.sign(payload=payload, secret=secret)
            return hmac.compare_digest(str(signature), str(expected))
        except Exception:
            return False