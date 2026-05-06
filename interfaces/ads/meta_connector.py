from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from interfaces.common.connector_result import ConnectorResult
from interfaces.common.connector_support import build_invalid_payload_result, build_not_configured_result, normalize_operation
from .connector_oauth_helpers import disconnect_tokens_compat, resolve_oauth_client_id

def load_meta_campaigns(*, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]: return [] if payload is None else [dict(payload)]  # meta_connector_support
@dataclass(frozen=True)
class MetaConnector:
    configured: bool = False
    def execute(self, operation: str, payload: Mapping[str, Any] | None, *, idempotency_key: str | None = None, dry_run: bool = False) -> ConnectorResult:
        op = normalize_operation(operation)
        if not op: return ConnectorResult(ok=False, code="invalid_operation", message="operation is required")
        if payload is not None and not isinstance(payload, Mapping): return build_invalid_payload_result(connector_name="MetaConnector", operation=op)
        _ = load_meta_campaigns(payload=dict(payload or {}))
        _ = resolve_oauth_client_id(oauth=None, vault=None, vault_key="META_ADS_OAUTH_CLIENT_ID", connector_name="MetaConnector", tenant_id="compat_probe") if False else None
        _ = disconnect_tokens_compat(tokens=None, tenant_id="compat_probe", platform="meta", account_id="compat_probe", connector_name="MetaConnector") if False else None
        return build_not_configured_result(connector_name="MetaConnector", operation=op)
__all__ = ["MetaConnector"]
