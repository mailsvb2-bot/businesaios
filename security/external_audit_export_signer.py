from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path


CANON_EXTERNAL_AUDIT_EXPORT_SIGNER = True


class ExternalAuditExportSigner:
    def __init__(self, shared_secret: str) -> None:
        self._secret = str(shared_secret).encode('utf-8')

    def sign_payload(self, *, payload: dict) -> dict[str, object]:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(self._secret, canonical.encode('utf-8'), hashlib.sha256).hexdigest()
        return {'payload': payload, 'signature': signature}

    def sign_file(self, *, input_path: str, output_path: str) -> str:
        payload = json.loads(Path(input_path).read_text(encoding='utf-8'))
        signed = self.sign_payload(payload=payload)
        Path(output_path).write_text(json.dumps(signed, ensure_ascii=False, indent=2), encoding='utf-8')
        return output_path


__all__ = [
    'CANON_EXTERNAL_AUDIT_EXPORT_SIGNER',
    'ExternalAuditExportSigner',
]
