from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Mapping


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


@dataclass(frozen=True)
class SignedAnalyticsExport:
    algorithm: str
    content_sha256: str
    signature_hex: str
    signer_key_id: str


class AnalyticsExportSignatureService:
    def sign_payload(self, *, payload: Mapping[str, Any], secret: str, signer_key_id: str = 'analytics-default') -> SignedAnalyticsExport:
        body = _canonical_json_bytes(payload)
        digest = hashlib.sha256(body).hexdigest()
        signature = hmac.new(str(secret).encode('utf-8'), body, digestmod=hashlib.sha256).hexdigest()
        return SignedAnalyticsExport(algorithm='HMAC-SHA256', content_sha256=digest, signature_hex=signature, signer_key_id=str(signer_key_id))

    def verify_payload(self, *, payload: Mapping[str, Any], secret: str, signature_hex: str) -> bool:
        body = _canonical_json_bytes(payload)
        expected = hmac.new(str(secret).encode('utf-8'), body, digestmod=hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, str(signature_hex))
