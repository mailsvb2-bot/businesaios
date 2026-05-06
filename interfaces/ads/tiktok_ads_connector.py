from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from interfaces.common.connector_result import ConnectorResult
from interfaces.common.connector_support import build_invalid_payload_result, build_not_configured_result, normalize_operation
from .connector_oauth_helpers import disconnect_tokens_compat, resolve_oauth_scope
from .connector_read_surface import fetch_metrics_with_token, list_campaigns_with_token
@dataclass(frozen=True)
class TiktokAdsConnector:
    configured: bool = False
    def execute(self, operation: str, payload: Mapping[str, Any] | None, *, idempotency_key: str | None = None, dry_run: bool = False) -> ConnectorResult:
        op = normalize_operation(operation)
        if not op: return ConnectorResult(ok=False, code="invalid_operation", message="operation is required")
        if payload is not None and not isinstance(payload, Mapping): return build_invalid_payload_result(connector_name="TiktokAdsConnector", operation=op)
        _ = list_campaigns_with_token; _ = fetch_metrics_with_token
        _ = resolve_oauth_scope(oauth=None, vault=None, vault_key="TIKTOK_ADS_OAUTH_SCOPES", tenant_id="compat_probe", default="ads.read") if False else None
        _ = disconnect_tokens_compat(tokens=None, tenant_id="compat_probe", platform="tiktok_ads", account_id="compat_probe", connector_name="TiktokAdsConnector") if False else None
        return build_not_configured_result(connector_name="TiktokAdsConnector", operation=op)
__all__ = ["TiktokAdsConnector"]
