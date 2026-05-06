from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from application.analytics.analytics_signing_key_resolver import AnalyticsSigningKeyResolver
from observability.analytics_export_signature import AnalyticsExportSignatureService


@dataclass(frozen=True)
class AnalyticsSignedExportService:
    key_resolver: AnalyticsSigningKeyResolver = AnalyticsSigningKeyResolver()
    _signer: AnalyticsExportSignatureService = AnalyticsExportSignatureService()

    def export_signed_bundle(self, *, export_dir: str, export_id: str, tenant_id: str, bundle: dict[str, Any]) -> dict[str, str]:
        signer_key_id, secret = self.key_resolver.resolve_or_issue(tenant_id=str(tenant_id))
        signed = self._signer.sign_payload(payload=bundle, secret=secret, signer_key_id=signer_key_id)
        path = Path(export_dir)
        path.mkdir(parents=True, exist_ok=True)
        bundle_file = path / f'{export_id}.bundle.json'
        manifest_file = path / f'{export_id}.manifest.json'
        bundle_file.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
        manifest = {
            'export_id': str(export_id),
            'tenant_id': str(tenant_id),
            'exported_at': datetime.now(UTC).isoformat(),
            'bundle_sha256': signed.content_sha256,
            'signature_algorithm': signed.algorithm,
            'signature_hex': signed.signature_hex,
            'signer_key_id': signed.signer_key_id,
        }
        manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
        return {'bundle_file': str(bundle_file), 'manifest_file': str(manifest_file), 'bundle_sha256': signed.content_sha256, 'signature_hex': signed.signature_hex, 'signer_key_id': signed.signer_key_id}
