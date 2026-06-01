from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_maturity import ConnectorMaturity
from interfaces.common.connector_result import ConnectorResult
from interfaces.common.connector_support import (
    build_invalid_payload_result,
    build_not_configured_result,
    normalize_operation,
)


@dataclass(frozen=True)
class MetaAdsConnector:
    configured: bool = False

    def connector_maturity(self) -> ConnectorMaturity:
        return ConnectorMaturity.PLACEHOLDER

    def connector_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            read=False,
            write=False,
            verify=False,
            dry_run=True,
            idempotent=False,
            metadata={"maturity": self.connector_maturity().value},
        )

    def execute(
        self,
        operation: str,
        payload: Mapping[str, Any] | None,
        *,
        idempotency_key: str | None = None,
        dry_run: bool = False,
    ) -> ConnectorResult:
        op = normalize_operation(operation)
        if not op:
            return ConnectorResult(ok=False, code="invalid_operation", message="operation is required")
        if payload is not None and not isinstance(payload, Mapping):
            return build_invalid_payload_result(connector_name="MetaAdsConnector", operation=op)
        return build_not_configured_result(connector_name="MetaAdsConnector", operation=op)


__all__ = ["MetaAdsConnector"]
