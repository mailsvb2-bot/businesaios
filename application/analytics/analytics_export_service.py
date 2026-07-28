from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from application.analytics.analytics_export_path_policy import AnalyticsExportPathPolicy, default_analytics_export_root


@dataclass(frozen=True)
class AnalyticsExportService:
    export_root: str | Path | None = None

    def _policy(self) -> AnalyticsExportPathPolicy:
        root = Path(self.export_root) if self.export_root is not None else default_analytics_export_root()
        return AnalyticsExportPathPolicy(export_root=root)

    def export_bundle(
        self,
        *,
        export_path: str | None,
        bundle: dict[str, Any],
        tenant_id: str,
        export_kind: str = 'analytics_dashboard_bundle',
    ) -> str:
        path = self._policy().resolve_file(requested_path=export_path, tenant_id=tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'tenant_id': str(tenant_id),
            'export_kind': str(export_kind),
            'exported_at': datetime.now(UTC).isoformat(),
            'bundle': bundle,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
        return str(path)
