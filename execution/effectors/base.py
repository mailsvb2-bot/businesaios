from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from interfaces.common.connector_result import ConnectorResult
from execution.effectors.result import EffectorResult


CANON_EFFECTOR_BASE = True


def _connector_capabilities_dict(connector: Any) -> dict[str, Any]:
    raw = getattr(connector, "capabilities", lambda: {})()
    if isinstance(raw, Mapping):
        data = dict(raw)
    else:
        data = {}
    defaults = {
        "read": True,
        "write": False,
        "verify": False,
        "dry_run": False,
        "idempotent": False,
        "reversible": False,
        "requires_human_approval": True,
        "evidence_fields": [],
    }
    defaults.update(data)
    defaults["evidence_fields"] = list(defaults.get("evidence_fields") or [])
    return defaults


@dataclass
class EffectorBase(ABC):
    action_type: str
    external_system: str

    @abstractmethod
    def execute(self, action: Mapping[str, Any]) -> EffectorResult:
        raise NotImplementedError

    def _action_ref(self, action: Mapping[str, Any]) -> str | None:
        action_id = str(action.get("action_id") or "").strip()
        return f"{self.external_system}:{self.action_type}:{action_id}" if action_id else None

    def _payload(self, action: Mapping[str, Any]) -> dict[str, Any]:
        payload = action.get("payload")
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _dry_run(self, action: Mapping[str, Any]) -> bool:
        payload = self._payload(action)
        raw = payload.get("dry_run", action.get("dry_run", False))
        return bool(raw)

    def _idempotency_key(self, action: Mapping[str, Any]) -> str | None:
        payload = self._payload(action)
        value = payload.get("idempotency_key", action.get("idempotency_key"))
        text = str(value or "").strip()
        return text or None

    def _base_evidence(
        self,
        action: Mapping[str, Any],
        *,
        connector_code: str,
        connector_message: str,
    ) -> dict[str, Any]:
        payload = self._payload(action)
        return {
            "action_type": str(self.action_type),
            "channel": str(action.get("channel") or ""),
            "decision_id": str(action.get("decision_id") or ""),
            "correlation_id": str(action.get("correlation_id") or ""),
            "connector_code": str(connector_code),
            "connector_message": str(connector_message),
            "requested_payload_keys": sorted(str(k) for k in payload.keys()),
        }


@dataclass
class ConnectorEffectorBase(EffectorBase):
    connector: Any
    operation: str

    def execute(self, action: Mapping[str, Any]) -> EffectorResult:
        payload = self._payload(action)
        dry_run = self._dry_run(action)
        idempotency_key = self._idempotency_key(action)
        result = self.connector.execute(
            self.operation,
            payload,
            idempotency_key=idempotency_key,
            dry_run=dry_run,
        )
        if not isinstance(result, ConnectorResult):
            return self._fail_closed(
                action,
                code="invalid_connector_result",
                message="connector returned invalid result",
                retry_kind="non_recoverable",
                operator_required=False,
                extra_payload={"connector_result_type": type(result).__name__},
            )

        code = str(result.code or "unknown")
        message = str(result.message or code)
        connector_payload = dict(result.payload or {})
        verify_result = None
        verified = False
        if bool(result.ok) and not bool(dry_run) and hasattr(self.connector, "supports_verify") and self.connector.supports_verify():
            verify_result = self.connector.verify(self.operation, payload, connector_payload)
            verified = isinstance(verify_result, ConnectorResult) and bool(verify_result.ok)
        if bool(result.ok):
            evidence = {
                **self._base_evidence(action, connector_code=code, connector_message=message),
                "connector_payload": connector_payload,
                "connector_capabilities": _connector_capabilities_dict(self.connector),
                "dry_run": bool(dry_run),
            }
            if idempotency_key:
                evidence["idempotency_key"] = idempotency_key
            if isinstance(verify_result, ConnectorResult):
                evidence["verify"] = {
                    "ok": bool(verify_result.ok),
                    "code": str(verify_result.code),
                    "message": str(verify_result.message),
                    "payload": dict(verify_result.payload or {}),
                }
            return EffectorResult(
                attempted=True,
                executed=True,
                verified=bool(verified),
                status="executed" if verified else "executed_unverified",
                external_system=self.external_system,
                external_ref=self._action_ref(action),
                code=code,
                message=message,
                operator_required=False,
                retry_kind="non_recoverable",
                payload={"connector_payload": connector_payload},
                evidence=evidence,
            )

        if code in {"not_configured", "missing_credentials", "approval_required", "not_implemented", "connector_not_available", "dry_run_not_supported", "idempotency_not_supported", "verify_not_supported"}:
            return self._fail_closed(
                action,
                code=code,
                message=message,
                retry_kind="operator_required",
                operator_required=True,
                extra_payload={"connector_payload": connector_payload},
            )
        if code in {"rate_limited", "temporary_unavailable", "network_error"}:
            return self._fail_closed(
                action,
                code=code,
                message=message,
                retry_kind="recoverable",
                operator_required=False,
                extra_payload={"connector_payload": connector_payload},
            )
        return self._fail_closed(
            action,
            code=code,
            message=message,
            retry_kind="non_recoverable",
            operator_required=False,
            extra_payload={"connector_payload": connector_payload},
        )

    def _fail_closed(
        self,
        action: Mapping[str, Any],
        *,
        code: str,
        message: str,
        retry_kind: str,
        operator_required: bool,
        extra_payload: dict[str, Any] | None = None,
    ) -> EffectorResult:
        evidence = self._base_evidence(action, connector_code=code, connector_message=message)
        evidence["connector_capabilities"] = _connector_capabilities_dict(self.connector)
        if extra_payload:
            evidence.update(extra_payload)
        return EffectorResult(
            attempted=True,
            executed=False,
            verified=False,
            status="operator_required" if operator_required else "failed",
            external_system=self.external_system,
            external_ref=self._action_ref(action),
            code=code,
            message=message,
            operator_required=operator_required,
            retry_kind=retry_kind,
            payload=dict(extra_payload or {}),
            evidence=evidence,
        )


__all__ = ["CANON_EFFECTOR_BASE", "EffectorBase", "ConnectorEffectorBase"]
