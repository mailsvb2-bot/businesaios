from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AnalyticsExportService:
    def export_bundle(self, *, export_path: str, bundle: dict[str, Any], tenant_id: str, export_kind: str = 'analytics_dashboard_bundle') -> str:
        path = Path(export_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'tenant_id': str(tenant_id), 'export_kind': str(export_kind), 'exported_at': datetime.now(UTC).isoformat(), 'bundle': bundle}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
        return str(path)
