from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from interfaces.common.auth_session import AuthSession
from interfaces.common.canonical_connector_contract import canonical_connector_contract
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_health import ConnectorHealth
from interfaces.common.connector_maturity import ConnectorMaturity
from interfaces.common.connector_result import ConnectorResult
from interfaces.common.connector_support import (
    build_health,
    build_invalid_payload_result,
    build_not_configured_result,
    connector_mode,
    normalize_operation,
    normalize_payload,
)
from interfaces.common.connector_truth import connector_truth_payload
from interfaces.common.rate_limit_guard import RateLimitGuard


@dataclass
class BaseConnector:
    connector_name: str = "base_connector"
    session: AuthSession = field(default_factory=AuthSession)
    rate_limit_guard: RateLimitGuard = field(default_factory=RateLimitGuard)

    @property
    def mode(self) -> str:
        return connector_mode(configured=self.session.configured)

    def connector_maturity(self) -> ConnectorMaturity:
        return ConnectorMaturity.PLACEHOLDER

    def connector_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(metadata={"maturity": self.connector_maturity().value})

    def capabilities(self) -> dict[str, Any]:
        return self.connector_capabilities().as_dict()

    def supports_write(self) -> bool:
        return bool(self.connector_capabilities().write)

    def supports_verify(self) -> bool:
        return bool(self.connector_capabilities().verify)

    def supports_dry_run(self) -> bool:
        return bool(self.connector_capabilities().dry_run)

    def supports_idempotency(self) -> bool:
        return bool(self.connector_capabilities().idempotent)

    def health(self) -> ConnectorHealth:
        capabilities = self.capabilities()
        health = build_health(
            connector_name=self.connector_name,
            configured=self.session.configured,
            maturity=self.connector_maturity().value,
            supports_write=bool(capabilities.get("write")),
            supports_verify=bool(capabilities.get("verify")),
        )
        health.metadata["capabilities"] = capabilities
        health.metadata["capability_contract"] = canonical_connector_contract(
            connector_name=self.connector_name,
            maturity=self.connector_maturity().value,
            configured=bool(self.session.configured),
            mode=self.mode,
            capabilities=capabilities,
        )
        return health

    def execute(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        dry_run: bool = False,
    ) -> ConnectorResult:
        if hasattr(self, "decide"):
            raise RuntimeError("connectors must never expose decide()")
        op = normalize_operation(operation)
        if not op:
            return ConnectorResult(ok=False, code="invalid_operation", message="operation is required")
        normalized_payload = normalize_payload(payload)
        if normalized_payload is None:
            return build_invalid_payload_result(connector_name=self.connector_name, operation=op)
        if not self.rate_limit_guard.allow(f"{self.connector_name}:{op}"):
            return ConnectorResult(ok=False, code="rate_limited", message="connector rate limit reached")
        if dry_run and not self.supports_dry_run():
            return self._enrich_result(
                ConnectorResult(
                    ok=False,
                    code="dry_run_not_supported",
                    message=f"{self.connector_name}.{op} does not support dry_run",
                    payload={
                        "operation": op,
                        "mode": self.mode,
                        "dry_run": True,
                        "capabilities": self.capabilities(),
                    },
                ),
                operation=op,
                dry_run=True,
                idempotency_key=idempotency_key,
            )
        if idempotency_key and not self.supports_idempotency():
            return self._enrich_result(
                ConnectorResult(
                    ok=False,
                    code="idempotency_not_supported",
                    message=f"{self.connector_name}.{op} does not support idempotency",
                    payload={
                        "operation": op,
                        "mode": self.mode,
                        "idempotency_key": str(idempotency_key),
                        "capabilities": self.capabilities(),
                    },
                ),
                operation=op,
                dry_run=bool(dry_run),
                idempotency_key=idempotency_key,
            )
        if not self.session.configured:
            result = build_not_configured_result(connector_name=self.connector_name, operation=op)
        else:
            result = self._execute_configured(
                op,
                normalized_payload,
                idempotency_key=idempotency_key,
                dry_run=bool(dry_run),
            )
        return self._enrich_result(
            result,
            operation=op,
            dry_run=bool(dry_run),
            idempotency_key=idempotency_key,
        )

    def verify(
        self,
        operation: str,
        payload: dict[str, Any],
        result_payload: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        op = normalize_operation(operation)
        normalized_payload = normalize_payload(payload)
        normalized_result_payload = normalize_payload(result_payload) or {}
        if not op:
            return ConnectorResult(ok=False, code="invalid_operation", message="operation is required")
        if normalized_payload is None:
            return build_invalid_payload_result(connector_name=self.connector_name, operation=op)
        if not self.supports_verify():
            return self._enrich_result(
                ConnectorResult(
                    ok=False,
                    code="verify_not_supported",
                    message=f"{self.connector_name}.{op} does not support verify",
                    payload={
                        "operation": op,
                        "result_payload": normalized_result_payload,
                        "capabilities": self.capabilities(),
                    },
                ),
                operation=op,
                dry_run=False,
                idempotency_key=None,
            )
        if not self.session.configured:
            return build_not_configured_result(connector_name=self.connector_name, operation=op)
        result = self._verify_configured(op, normalized_payload, normalized_result_payload)
        return self._enrich_result(result, operation=op, dry_run=False, idempotency_key=None)

    def _execute_configured(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        dry_run: bool = False,
    ) -> ConnectorResult:
        return ConnectorResult(ok=False, code="not_implemented", message=f"{operation} is not implemented yet")

    def _verify_configured(
        self,
        operation: str,
        payload: dict[str, Any],
        result_payload: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        return ConnectorResult(ok=False, code="verify_not_supported", message=f"{operation} verify is not implemented yet")

    def _enrich_result(
        self,
        result: ConnectorResult,
        *,
        operation: str,
        dry_run: bool,
        idempotency_key: str | None,
    ) -> ConnectorResult:
        payload = connector_truth_payload(
            connector_name=str(self.connector_name),
            configured=bool(self.session.configured),
            capabilities=self.connector_capabilities(),
            operation=str(operation),
            dry_run=bool(dry_run),
            idempotency_key=idempotency_key,
            payload=dict(result.payload or {}),
        )
        return ConnectorResult(
            ok=bool(result.ok),
            code=str(result.code),
            message=str(result.message or result.code),
            payload=payload,
        )
