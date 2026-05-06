from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from security.payload_redaction import PayloadRedactor
from tenancy.tenant_context import TenantRequestContext


CANON_REQUEST_CONTEXT = True


@dataclass(frozen=True)
class RequestContext:
    request_id: str | None = None
    correlation_id: str | None = None
    tenant_id: str | None = None
    actor_id: str | None = None
    session_id: str | None = None
    subject: str | None = None
    audience: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    token_scopes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    _generated_request_id: str | None = field(default=None, init=False, repr=False, compare=False)
    _generated_correlation_id: str | None = field(default=None, init=False, repr=False, compare=False)

    def normalized_request_id(self) -> str:
        value = str(self.request_id or '').strip()
        if value:
            return value
        cached = str(self._generated_request_id or '').strip()
        if cached:
            return cached
        generated = str(uuid4())
        object.__setattr__(self, '_generated_request_id', generated)
        return generated

    def normalized_correlation_id(self) -> str:
        value = str(self.correlation_id or '').strip()
        if value:
            return value
        cached = str(self._generated_correlation_id or '').strip()
        if cached:
            return cached
        generated = self.normalized_request_id()
        object.__setattr__(self, '_generated_correlation_id', generated)
        return generated

    def validated_tenant_id(self, *, required: bool = False) -> str | None:
        value = normalize_tenant_id(self.tenant_id)
        if required:
            return require_tenant_id(value)
        return value or None

    def tenant_context(self, *, required: bool = False) -> TenantRequestContext | None:
        tenant_id = self.validated_tenant_id(required=required)
        if not tenant_id:
            return None
        return TenantRequestContext(
            tenant_id=tenant_id,
            actor_id=self.actor_id,
            request_id=self.normalized_request_id(),
            trace_id=self.normalized_correlation_id(),
            metadata=dict(self.metadata),
        )

    def with_metadata(self, **items: Any) -> RequestContext:
        merged = dict(self.metadata)
        merged.update(items)
        derived = RequestContext(
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            session_id=self.session_id,
            subject=self.subject,
            audience=self.audience,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            token_scopes=tuple(self.token_scopes),
            metadata=merged,
        )
        object.__setattr__(derived, '_generated_request_id', self._generated_request_id)
        object.__setattr__(derived, '_generated_correlation_id', self._generated_correlation_id)
        return derived

    def redacted_dict(self, *, redactor: PayloadRedactor | None = None) -> dict[str, Any]:
        payload = {
            'request_id': self.normalized_request_id(),
            'correlation_id': self.normalized_correlation_id(),
            'tenant_id': self.validated_tenant_id(required=False),
            'actor_id': self.actor_id,
            'session_id': self.session_id,
            'subject': self.subject,
            'audience': self.audience,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'token_scopes': list(self.token_scopes),
            'metadata': dict(self.metadata),
        }
        return (redactor or PayloadRedactor()).redact(payload)

    @classmethod
    def from_headers(
        cls,
        headers: Mapping[str, Any] | None,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> RequestContext:
        normalized_headers = {str(k).lower(): v for k, v in dict(headers or {}).items()}
        scopes_raw = normalized_headers.get('x-token-scopes') or normalized_headers.get('scope') or ''
        if isinstance(scopes_raw, str):
            scopes = tuple(part for part in scopes_raw.replace(',', ' ').split() if part)
        else:
            scopes = tuple(str(item) for item in scopes_raw)
        forwarded_for = str(normalized_headers.get('x-forwarded-for') or '').split(',')[0].strip() or None
        return cls(
            request_id=_first_header(normalized_headers, 'x-request-id', 'request-id'),
            correlation_id=_first_header(normalized_headers, 'x-correlation-id', 'correlation-id'),
            tenant_id=_normalized_optional_tenant(
                _first_header(normalized_headers, 'x-tenant-id', 'tenant-id')
            ),
            actor_id=_first_header(normalized_headers, 'x-actor-id', 'actor-id', 'x-user-id'),
            session_id=_first_header(normalized_headers, 'x-session-id', 'session-id'),
            subject=_first_header(normalized_headers, 'x-auth-subject', 'x-subject'),
            audience=_first_header(normalized_headers, 'x-auth-audience', 'x-audience'),
            ip_address=forwarded_for or _first_header(normalized_headers, 'x-real-ip'),
            user_agent=_first_header(normalized_headers, 'user-agent'),
            token_scopes=scopes,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def from_http_request(cls, request: Any, *, metadata: Mapping[str, Any] | None = None) -> RequestContext:
        request_headers = getattr(request, 'headers', {})
        url = getattr(request, 'url', None)
        client = getattr(request, 'client', None)
        header_get = getattr(request_headers, 'get', lambda *_: None)
        forwarded_proto = str(header_get('x-forwarded-proto') or header_get('x-forwarded-protocol') or '').split(',')[0].strip().lower()
        scheme = forwarded_proto or str(getattr(url, 'scheme', '') or '').strip().lower()
        merged_metadata = {
            'scheme': scheme or getattr(url, 'scheme', None),
            'transport_encrypted': scheme == 'https',
            'method': getattr(request, 'method', None),
            'path': getattr(url, 'path', None),
            'request_rate': header_get('x-request-rate'),
            'region_hint': header_get('x-region-hint'),
            **dict(metadata or {}),
        }
        context = cls.from_headers(request_headers, metadata=merged_metadata)
        if context.ip_address:
            return context
        client_host = getattr(client, 'host', None) if client is not None else None
        if client_host is None:
            return context
        return RequestContext(
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            session_id=context.session_id,
            subject=context.subject,
            audience=context.audience,
            ip_address=str(client_host),
            user_agent=context.user_agent,
            token_scopes=context.token_scopes,
            metadata=dict(context.metadata),
        )


def _first_header(headers: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = headers.get(str(name).lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _normalized_optional_tenant(value: Any) -> str | None:
    normalized = normalize_tenant_id(value)
    return normalized or None
