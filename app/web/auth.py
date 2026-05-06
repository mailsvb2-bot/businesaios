from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from security.key_management_contract import KeyPurpose, KeyStatus
from security.key_provider import KeyProvider, build_default_key_provider
from security.payload_redaction import PayloadRedactor
from security.token_policy import TokenPolicy


@dataclass
class AuthService:
    token_policy: TokenPolicy = field(default_factory=TokenPolicy)
    key_provider: KeyProvider | None = None
    redactor: PayloadRedactor = field(default_factory=PayloadRedactor)

    def __post_init__(self) -> None:
        if self.key_provider is None:
            self.key_provider = build_default_key_provider()

    def authenticate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        now = _parse_dt(data.get("now"), fallback=datetime.now(timezone.utc))
        issued_at = _parse_dt(data.get("issued_at"), fallback=now)
        expires_at = _parse_dt(data.get("expires_at"), fallback=now)
        scopes = _normalize_scopes(data.get('scopes'))
        verdict = self.token_policy.evaluate(
            issued_at=issued_at,
            expires_at=expires_at,
            now=now,
            scopes=scopes,
            subject=str(data.get("subject") or "") or None,
            audience=str(data.get("audience") or "") or None,
            issuer=str(data.get("issuer") or "") or None,
            session_id=str(data.get("session_id") or "") or None,
            algorithm=str(data.get("algorithm") or "") or None,
            key_id=str(data.get("key_id") or "") or None,
            token_id=str(data.get("token_id") or "") or None,
        )
        redacted = self.redactor.redact(data)
        key_context = _evaluate_signing_material(
            key_provider=self.key_provider,
            key_id=data.get('key_id'),
            tenant_id=data.get('tenant_id'),
            connector_id=data.get('connector_id'),
        )
        if verdict.allowed and not key_context['allowed']:
            verdict = type(verdict)(allowed=False, reason=str(key_context['signing_material_reason']), requires_reissue=False, labels=dict(verdict.labels))
        ttl_seconds = max(0, int((expires_at - now).total_seconds())) if verdict.allowed else None
        redacted["security"] = {
            "token": {
                "allowed": verdict.allowed,
                "reason": verdict.reason,
                "requires_reissue": verdict.requires_reissue,
                "labels": dict(verdict.labels),
                "scopes": list(scopes),
                "ttl_seconds": ttl_seconds,
            },
            "tenant": {"bound": bool(str(data.get("tenant_id") or "").strip())},
        }
        redacted['auth_context'] = key_context
        return {"kind": "auth_result", "payload": redacted}


def _normalize_scopes(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw = value.replace(',', ' ').split()
    elif isinstance(value, (list, tuple, set)):
        raw = [str(item) for item in value]
    else:
        raw = []
    deduped: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in deduped:
            deduped.append(text)
    return tuple(deduped)


def _parse_dt(value: Any, *, fallback: datetime) -> datetime:
    text = str(value or "").strip()
    if not text:
        return fallback
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _evaluate_signing_material(
    *,
    key_provider: KeyProvider | None,
    key_id: Any,
    tenant_id: Any,
    connector_id: Any,
) -> dict[str, Any]:
    key_text = str(key_id or '').strip()
    tenant_text = str(tenant_id or '').strip() or None
    connector_text = str(connector_id or '').strip() or None
    base = {
        'signing_material_registered': False,
        'signing_material_purpose_allowed': False,
        'signing_material_active': False,
        'signing_material_reason': 'missing_key_id' if not key_text else 'ok',
        'allowed': not key_text,
        'key_id': key_text or None,
    }
    if not key_text:
        return base
    if key_provider is None:
        return {**base, 'signing_material_reason': 'missing_key_provider', 'allowed': False}
    try:
        record = key_provider.get(key_text)
    except KeyError:
        return {**base, 'signing_material_reason': 'unknown_key_id', 'allowed': False}
    base['signing_material_registered'] = True
    if record.purpose not in {KeyPurpose.REQUEST_SIGNING, KeyPurpose.TOKEN_SIGNING, KeyPurpose.SESSION_SIGNING}:
        return {**base, 'signing_material_reason': 'key_purpose_not_allowed', 'allowed': False}
    base['signing_material_purpose_allowed'] = True
    if tenant_text and record.tenant_id not in {None, tenant_text}:
        return {**base, 'signing_material_reason': 'key_tenant_mismatch', 'allowed': False}
    if connector_text and record.connector_id not in {None, connector_text}:
        return {**base, 'signing_material_reason': 'key_connector_mismatch', 'allowed': False}
    if record.status is not KeyStatus.ACTIVE:
        return {**base, 'signing_material_reason': 'key_not_active', 'allowed': False}
    base['signing_material_active'] = True
    return {**base, 'signing_material_reason': 'ok', 'allowed': True}


__all__ = ["AuthService"]
