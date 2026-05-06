from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from application.analytics.analytics_manifest_chain_store import SqliteAnalyticsManifestChainStore
from application.analytics.analytics_signed_export_service import AnalyticsSignedExportService
from application.analytics.analytics_signing_key_resolver import AnalyticsSigningKeyResolver


@dataclass(frozen=True)
class AnalyticsSignedExportChainService:
    manifest_chain_store: SqliteAnalyticsManifestChainStore
    key_resolver: AnalyticsSigningKeyResolver = AnalyticsSigningKeyResolver()
    _signed_export: AnalyticsSignedExportService = AnalyticsSignedExportService()

    def export_signed_bundle(self, *, export_dir: str, export_id: str, tenant_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
        result = self._signed_export.export_signed_bundle(
            export_dir=export_dir,
            export_id=export_id,
            tenant_id=str(tenant_id),
            bundle=bundle,
        )
        manifest_path = result["manifest_file"]
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest_payload = json.load(fh)
        chain_record = self.manifest_chain_store.put(
            export_id=str(export_id),
            tenant_id=str(tenant_id),
            manifest_payload=manifest_payload,
            created_at=str(manifest_payload["exported_at"]),
        )
        manifest_payload["previous_manifest_sha256"] = chain_record.previous_manifest_sha256
        manifest_payload["manifest_chain_sha256"] = chain_record.manifest_sha256
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest_payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        return {
            **result,
            "previous_manifest_sha256": chain_record.previous_manifest_sha256,
            "manifest_chain_sha256": chain_record.manifest_sha256,
        }
