from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

CANON_IMMUTABLE_AUDIT_BUNDLE = True

class ImmutableAuditBundleBuilder:
    def build(self, *, signed_payload: Mapping[str, Any], certification: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = {'schema_version': 1, 'bundle_kind': 'security_audit_export', 'signed_payload': dict(signed_payload), 'certification': dict(certification or {})}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return {**payload, 'bundle_digest': hashlib.sha256(canonical.encode('utf-8')).hexdigest()}

    def verify(self, *, bundle: Mapping[str, Any]) -> bool:
        candidate = {'schema_version': int(bundle.get('schema_version') or 0), 'bundle_kind': str(bundle.get('bundle_kind') or ''), 'signed_payload': dict(bundle.get('signed_payload') or {}), 'certification': dict(bundle.get('certification') or {})}
        canonical = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        expected = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        return expected == str(bundle.get('bundle_digest') or '')

__all__ = ['CANON_IMMUTABLE_AUDIT_BUNDLE', 'ImmutableAuditBundleBuilder']
