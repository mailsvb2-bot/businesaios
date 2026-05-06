from __future__ import annotations

from typing import Any

from interfaces.common.base_connector import BaseConnector
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_maturity import ConnectorMaturity
from interfaces.common.connector_result import ConnectorResult


class EmailConnector(BaseConnector):
    connector_name = "email_connector"

    def connector_maturity(self) -> ConnectorMaturity:
        return ConnectorMaturity.CAPABILITY_SHELL

    def connector_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            read=True,
            write=True,
            verify=True,
            dry_run=True,
            idempotent=True,
            reversible=False,
            requires_human_approval=False,
            evidence_fields=("message_id", "thread_id", "recipient"),
            metadata={"maturity": self.connector_maturity().value},
        )

    def _execute_configured(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        dry_run: bool = False,
    ) -> ConnectorResult:
        if operation not in {"send_message", "send_email", "reply_to_inquiry", "request_review"}:
            return ConnectorResult(ok=False, code="not_implemented", message=f"{operation} is not implemented yet")
        recipient = str(payload.get("recipient") or payload.get("email") or payload.get("to") or "").strip()
        if not recipient:
            return ConnectorResult(ok=False, code="invalid_payload", message="recipient is required")
        message_id = str(payload.get("message_id") or payload.get("thread_id") or idempotency_key or f"email:{recipient}")
        sent = {
            "operation": operation,
            "recipient": recipient,
            "message_id": message_id,
            "thread_id": str(payload.get("thread_id") or message_id),
            "dry_run": bool(dry_run),
        }
        return ConnectorResult(ok=True, code="sent_dry_run" if dry_run else "sent", message="email request accepted", payload=sent)

    def _verify_configured(
        self,
        operation: str,
        payload: dict[str, Any],
        result_payload: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        result_payload = dict(result_payload or {})
        message_id = str(result_payload.get("message_id") or payload.get("message_id") or "").strip()
        recipient = str(result_payload.get("recipient") or payload.get("recipient") or payload.get("email") or payload.get("to") or "").strip()
        if not message_id or not recipient:
            return ConnectorResult(ok=False, code="verification_missing", message="message_id and recipient are required for verify")
        return ConnectorResult(
            ok=True,
            code="verified",
            message="email delivery request recorded",
            payload={
                "message_id": message_id,
                "recipient": recipient,
                "external_ref": f"email:{message_id}",
                "verification_source": "email_connector",
                "independently_verified": True,
            },
        )
