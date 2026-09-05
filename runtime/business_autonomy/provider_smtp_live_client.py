from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from contracts.email_outbound import (
    EmailOutboundPayloadV1,
    normalize_email_address,
    normalize_smtp_host,
    normalize_smtp_port,
    normalize_smtp_security,
)
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.handler_loader import import_internal_attr
from security.secret_contract import SecretRef
from security.secret_vault import SecretVault

CANON_PROVIDER_SMTP_LIVE_CLIENT = True


@dataclass(frozen=True)
class ProviderSmtpLiveTransport:
    secret_vault: SecretVault
    bind_live_network: bool = False
    timeout_seconds: float = 20.0
    normalizers: ProviderPayloadNormalizers = field(default_factory=ProviderPayloadNormalizers)

    def execute(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        operation: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if provider.provider_key != "email_connector":
            raise ValueError("SMTP transport only owns email_connector")
        operation = str(operation or "").strip()
        if operation not in {"health_probe", "message_send"}:
            return self._prepared(operation=operation, reason="smtp_operation_not_live_supported")
        secrets = self._settings(provider=provider, tenant_id=tenant_id, business_id=business_id)
        try:
            settings = self._validated_settings(secrets)
        except ValueError as exc:
            return self._failure(
                code=str(exc), delivery_state="not_attempted", retryable=False, category="configuration"
            )
        allow_network = self.bind_live_network and bool(payload.get("_allow_network", False))
        if operation == "health_probe":
            if not allow_network:
                return self._prepared(operation=operation)
            return self._probe(settings)
        if not bool(payload.get("_provider_write_approved", False)):
            return self._prepared(operation=operation, reason="smtp_write_approval_required")
        normalized = self.normalizers.normalize_outbound(
            provider=provider,
            operation=operation,
            payload={key: value for key, value in payload.items() if not str(key).startswith("_")},
        )
        try:
            email = EmailOutboundPayloadV1(
                recipient=str(normalized.get("recipient") or ""),
                subject=str(normalized.get("subject") or ""),
                body=str(normalized.get("body") or ""),
            )
        except ValueError as exc:
            return self._failure(
                code=str(exc), delivery_state="not_attempted", retryable=False, category="validation"
            )
        queue_job_id = str(payload.get("_provider_queue_job_id") or "").strip()
        if not queue_job_id:
            return self._failure(
                code="smtp_queue_identity_missing", delivery_state="not_attempted", retryable=False, category="idempotency"
            )
        if not allow_network:
            return self._prepared(
                operation=operation,
                request={"recipient": email.recipient, "subject": email.subject, "body_length": len(email.body)},
            )
        send = import_internal_attr(
            "runtime._internal.effects_clients.provider_outbound_sender", "smtp_send_explicit"
        )
        error_type = import_internal_attr(
            "runtime._internal.effects_clients.provider_outbound_sender", "SmtpExplicitError"
        )
        try:
            result = send(
                **settings,
                recipient=email.recipient,
                subject=email.subject,
                body=email.body,
                idempotency_key=queue_job_id,
            )
        except error_type as exc:
            state = str(getattr(exc, "delivery_state", "unknown") or "unknown")
            code = str(getattr(exc, "code", "smtp_error") or "smtp_error")
            retryable = bool(getattr(exc, "retryable", False))
            category = "ambiguous_delivery" if state == "unknown" else ("provider_rejected" if state == "rejected" else "transport")
            return self._failure(
                code=None if state == "unknown" else code,
                delivery_state=state,
                retryable=retryable,
                category=category,
                internal_code=code,
            )
        message_id = str(result.get("message_id") or "").strip()
        return {
            "provider_key": provider.provider_key,
            "network_capable": True,
            "_response_ok": bool(result.get("accepted") and message_id),
            "parsed_response": {
                "ok": bool(result.get("accepted") and message_id),
                "resource_id": message_id or None,
                "error_code": None,
                "error_category": None,
                "retryable": False,
                "delivery_state": "accepted" if message_id else "unknown",
            },
            "smtp": {"accepted": bool(message_id), "delivered": False},
        }

    def _probe(self, settings: Mapping[str, Any]) -> Mapping[str, Any]:
        probe = import_internal_attr(
            "runtime._internal.effects_clients.provider_outbound_sender", "smtp_probe_explicit"
        )
        error_type = import_internal_attr(
            "runtime._internal.effects_clients.provider_outbound_sender", "SmtpExplicitError"
        )
        try:
            result = probe(**{key: settings[key] for key in ("host", "port", "security", "username", "password", "timeout_s")})
        except error_type as exc:
            return self._failure(
                code=str(getattr(exc, "code", "smtp_probe_failed")),
                delivery_state="not_attempted",
                retryable=bool(getattr(exc, "retryable", False)),
                category="probe",
            )
        return {
            "provider_key": "email_connector",
            "network_capable": True,
            "_response_ok": bool(result.get("ok")),
            "smtp": {"probe_ok": bool(result.get("ok")), "status": result.get("smtp_status")},
        }

    def _settings(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for name in ("smtp_host", "smtp_port", "smtp_username", "smtp_password", "api_token", "from_address", "smtp_security"):
            ref = SecretRef(
                tenant_id=str(tenant_id), connector_id=provider.connector_id, scope=str(business_id),
                secret_name=f"{provider.connector_id}.{name}",
            )
            try:
                values[name] = self.secret_vault.get(ref).decode("utf-8").strip()
            except Exception:
                values[name] = ""
        return values

    def _validated_settings(self, values: Mapping[str, str]) -> dict[str, Any]:
        username = str(values.get("smtp_username") or "").strip()
        password = str(values.get("smtp_password") or values.get("api_token") or "")
        if bool(username) != bool(password):
            raise ValueError("SMTP username and password must be configured together")
        return {
            "host": normalize_smtp_host(values.get("smtp_host")),
            "port": normalize_smtp_port(values.get("smtp_port")),
            "security": normalize_smtp_security(values.get("smtp_security")),
            "username": username,
            "password": password,
            "sender": normalize_email_address(values.get("from_address")),
            "timeout_s": max(0.1, min(120.0, float(self.timeout_seconds))),
        }

    @staticmethod
    def _prepared(*, operation: str, reason: str | None = None, request: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        return {
            "_prepared_only": True,
            "provider_key": "email_connector",
            "network_capable": True,
            "request": dict(request or {}),
            **({"reason": reason} if reason else {}),
        }

    @staticmethod
    def _failure(
        *, code: str | None, delivery_state: str, retryable: bool, category: str, internal_code: str | None = None
    ) -> Mapping[str, Any]:
        return {
            "provider_key": "email_connector",
            "network_capable": True,
            "_response_ok": False,
            "parsed_response": {
                "ok": False,
                "resource_id": None,
                "error_code": code,
                "error_category": category,
                "retryable": bool(retryable),
                "delivery_state": delivery_state,
            },
            "error_kind": internal_code or code or category,
            "error_message": category,
        }


__all__ = ["CANON_PROVIDER_SMTP_LIVE_CLIENT", "ProviderSmtpLiveTransport"]
