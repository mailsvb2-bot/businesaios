from __future__ import annotations

from typing import Any

from contracts.email_outbound import normalize_email_address
from interfaces.common.base_connector import BaseConnector
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_maturity import ConnectorMaturity
from interfaces.common.connector_result import ConnectorResult


class EmailConnector(BaseConnector):
    """Compatibility facade; live writes belong to the canonical provider queue."""

    connector_name = "email_connector"

    def connector_maturity(self) -> ConnectorMaturity:
        return ConnectorMaturity.CAPABILITY_SHELL

    def connector_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            read=False,
            write=True,
            verify=True,
            dry_run=True,
            idempotent=True,
            reversible=False,
            requires_human_approval=True,
            evidence_fields=("message_id", "recipient", "delivery_state"),
            metadata={
                "maturity": self.connector_maturity().value,
                "live_write_owner": "runtime.business_autonomy.provider_queue_execution",
            },
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
        try:
            recipient = normalize_email_address(
                payload.get("recipient") or payload.get("email") or payload.get("to") or ""
            )
        except ValueError:
            return ConnectorResult(ok=False, code="invalid_payload", message="valid recipient is required")
        message_id = str(payload.get("message_id") or payload.get("thread_id") or idempotency_key or "").strip()
        prepared = {
            "operation": operation,
            "recipient": recipient,
            "message_id": message_id or None,
            "dry_run": bool(dry_run),
            "delivery_state": "not_attempted",
        }
        if not dry_run:
            return ConnectorResult(
                ok=False,
                code="canonical_provider_runtime_required",
                message="live email must use the canonical provider queue",
                payload=prepared,
            )
        return ConnectorResult(
            ok=True,
            code="prepared_dry_run",
            message="email request prepared without provider I/O",
            payload=prepared,
        )

    def _verify_configured(
        self,
        operation: str,
        payload: dict[str, Any],
        result_payload: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        result_payload = dict(result_payload or {})
        provider_message_id = str(result_payload.get("provider_message_id") or "").strip()
        try:
            recipient = normalize_email_address(
                result_payload.get("recipient") or payload.get("recipient") or payload.get("email") or payload.get("to") or ""
            )
        except ValueError:
            recipient = ""
        if not provider_message_id or not recipient or not bool(result_payload.get("provider_accepted")):
            return ConnectorResult(
                ok=False,
                code="provider_evidence_required",
                message="canonical provider acceptance evidence is required",
            )
        return ConnectorResult(
            ok=True,
            code="provider_accepted",
            message="SMTP provider acceptance recorded; final delivery is not implied",
            payload={
                "message_id": provider_message_id,
                "recipient": recipient,
                "external_ref": f"email:{provider_message_id}",
                "delivery_state": "accepted",
                "independently_verified": False,
            },
        )
