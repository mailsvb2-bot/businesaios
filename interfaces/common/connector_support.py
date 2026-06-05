from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from interfaces.common.canonical_connector_contract import canonical_connector_contract
from interfaces.common.connector_health import ConnectorHealth
from interfaces.common.connector_result import ConnectorResult

STUB_MODE = "stub"
LIVE_MODE = "live"


def connector_mode(*, configured: bool) -> str:
    return LIVE_MODE if bool(configured) else STUB_MODE


def normalize_operation(value: Any) -> str:
    return str(value or "").strip()


def normalize_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return None


def build_health(
    *,
    connector_name: str,
    configured: bool,
    maturity: str = "placeholder",
    supports_write: bool = False,
    supports_verify: bool = False,
) -> ConnectorHealth:
    mode = connector_mode(configured=configured)
    capability_contract = canonical_connector_contract(
        connector_name=str(connector_name),
        maturity=str(maturity),
        configured=bool(configured),
        mode=mode,
        capabilities={
            "write": bool(supports_write),
            "verify": bool(supports_verify),
            "dry_run": False,
            "requires_human_approval": True,
        },
    )
    return ConnectorHealth(
        connector_name=str(connector_name),
        healthy=bool(configured),
        reason="" if configured else "not_configured",
        metadata={
            "mode": mode,
            "configured": bool(configured),
            "prod_ready": bool(configured and supports_write and supports_verify),
            "stub": mode == STUB_MODE,
            "maturity": str(maturity),
            "supports_write": bool(supports_write),
            "supports_verify": bool(supports_verify),
            "capability_contract": capability_contract,
        },
    )


def build_not_configured_result(*, connector_name: str, operation: str) -> ConnectorResult:
    return ConnectorResult(
        ok=False,
        code="not_configured",
        message=f"{connector_name} is a deliberate stub until credentials are provided",
        payload={"operation": str(operation), "configured": False, "mode": STUB_MODE},
    )


def build_invalid_payload_result(*, connector_name: str, operation: str) -> ConnectorResult:
    return ConnectorResult(
        ok=False,
        code="invalid_payload",
        message=f"{connector_name}.{operation} requires mapping payload",
        payload={"operation": str(operation)},
    )


__all__ = [
    "STUB_MODE",
    "LIVE_MODE",
    "connector_mode",
    "normalize_operation",
    "normalize_payload",
    "build_health",
    "build_not_configured_result",
    "build_invalid_payload_result",
]
