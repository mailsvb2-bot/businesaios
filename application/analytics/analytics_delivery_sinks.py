from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileDropAnalyticsSink:
    root_dir: str = "runtime/data/analytics_delivery"

    def deliver(self, *, tenant_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        tenant_dir = Path(self.root_dir) / str(tenant_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        kind = str(payload.get("kind") or "analytics_payload")
        out_file = tenant_dir / f"{kind}.json"
        out_file.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return {"delivered": True, "channel": "file_drop", "path": str(out_file)}


@dataclass(frozen=True)
class WebhookEnvelopeAnalyticsSink:
    def deliver(self, *, tenant_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "delivered": True,
            "channel": "webhook_envelope",
            "tenant_id": str(tenant_id),
            "envelope": {"kind": "analytics_delivery_webhook_envelope", "tenant_id": str(tenant_id), "payload": dict(payload)},
        }
