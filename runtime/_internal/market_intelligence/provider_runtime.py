from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from typing import Any, Mapping

from contracts.platforms.market_intelligence_provider_catalog import (
    PROVIDER_ALIASES,
    PROVIDER_CATALOG,
    operations_for_family,
)
from runtime._internal.market_intelligence.http_transport import HttpRequest, HttpTransportError
from runtime._internal.market_intelligence.provider_contracts import (
    ProviderAuthContract,
    ProviderAuthKind,
    ProviderCapabilityManifest,
    ProviderContractRegistry,
    ProviderErrorCode,
    ProviderRequestContract,
    ProviderSchemaContract,
)

CANON_MARKET_INTELLIGENCE_PROVIDER_RUNTIME = True


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


class ProviderRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, provider: str, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = _text(code, default=ProviderErrorCode.TRANSPORT_ERROR.value)
        self.provider = _text(provider)
        self.details = dict(details or {})


class SecretReader:
    def read(self, ref: str | None) -> str | None:
        key = _text(ref)
        if not key:
            return None
        return _text(os.getenv(key)) or None


@dataclass(frozen=True)
class ProviderRequestPlanV2:
    provider: str
    source_family: str
    operation: str
    request: HttpRequest
    item_path: str
    next_cursor_path: str
    page_size_param: str
    cursor_param: str
    max_pages: int
    version: str
    manifest: Mapping[str, Any]


@dataclass
class ProviderRuntimeFactory:
    registry: ProviderContractRegistry = field(default_factory=ProviderContractRegistry)
    secrets: SecretReader = field(default_factory=SecretReader)

    def __post_init__(self) -> None:
        self._bootstrap_defaults()

    def supports_provider(self, provider: str) -> bool:
        try:
            self.registry.manifest(provider)
            return True
        except KeyError:
            return False

    def build_plan(self, *, provider: str, operation: str, payload: Mapping[str, Any]) -> ProviderRequestPlanV2:
        canonical = self.registry.canonical_provider(provider)
        self.registry.validate_no_hidden_fallback(requested_provider=provider, resolved_provider=canonical)
        manifest = self.registry.manifest(canonical)
        request_contract = self.registry.request_contract(canonical, operation)
        schema = self.registry.schema_contract(canonical, operation)
        auth = self.registry.auth_contract(canonical)
        self._validate_payload(payload=payload, schema=schema, request_contract=request_contract)
        params = self._build_query_params(payload=payload, request_contract=request_contract, auth=auth)
        headers = self._build_headers(auth=auth, request_contract=request_contract)
        body = self._build_body(payload=payload, request_contract=request_contract)
        url = f"{request_contract.base_url.rstrip('/')}/{request_contract.path.lstrip('/')}"
        return ProviderRequestPlanV2(
            provider=canonical,
            source_family=manifest.source_family,
            operation=operation,
            request=HttpRequest(
                method=request_contract.method,
                url=url,
                params=params,
                headers=headers,
                body=body,
                timeout_seconds=float(payload.get('timeout_seconds') or 20.0),
            ),
            item_path=request_contract.item_path,
            next_cursor_path=request_contract.next_cursor_path,
            page_size_param=request_contract.page_size_param,
            cursor_param=request_contract.cursor_param,
            max_pages=max(1, int(payload.get('max_pages') or 20)),
            version=request_contract.version,
            manifest=manifest.as_dict(),
        )

    def normalize_records(self, *, provider: str, operation: str, source_family: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in records:
            row = dict(item or {})
            external_id = _text(row.get('external_id') or row.get('id') or row.get('uuid') or row.get('slug'))
            if not external_id:
                raise ProviderRuntimeError(
                    ProviderErrorCode.CONTRACT_VIOLATION.value,
                    'provider record has no stable identity',
                    provider=provider,
                    details={'operation': operation},
                )
            normalized.append(
                {
                    'provider': provider,
                    'source_family': source_family,
                    'external_id': external_id,
                    'title': _text(row.get('title') or row.get('name') or row.get('headline')),
                    'body': _text(row.get('body') or row.get('description') or row.get('text') or row.get('copy')),
                    'url': _text(row.get('url') or row.get('landing_url')) or None,
                    'price': row.get('price'),
                    'rating': row.get('rating'),
                    'currency': _text(row.get('currency')) or None,
                    'review_count': row.get('review_count'),
                    'published_at': _text(row.get('published_at') or row.get('created_at')) or None,
                    'updated_at': _text(row.get('updated_at')) or None,
                    'observed_at': _text(row.get('observed_at') or row.get('updated_at') or row.get('published_at')) or None,
                    'tags': tuple(sorted({str(x).strip().lower() for x in row.get('tags', ()) if str(x).strip()})),
                    'evidence': {
                        'provider_version': self.registry.manifest(provider).version,
                        'operation': operation,
                        'source_family': source_family,
                    },
                    'metadata': {
                        'raw_type': _text(row.get('type')),
                        'raw_status': _text(row.get('status')),
                    },
                }
            )
        return normalized

    def map_transport_error(self, *, provider: str, exc: Exception) -> ProviderRuntimeError:
        if isinstance(exc, HttpTransportError):
            status = exc.status_code
            if status == 401:
                return ProviderRuntimeError(ProviderErrorCode.AUTH_INVALID.value, str(exc), provider=provider, details=exc.payload)
            if status == 403:
                return ProviderRuntimeError(ProviderErrorCode.FORBIDDEN.value, str(exc), provider=provider, details=exc.payload)
            if status == 404:
                return ProviderRuntimeError(ProviderErrorCode.NOT_FOUND.value, str(exc), provider=provider, details=exc.payload)
            if status == 429:
                return ProviderRuntimeError(ProviderErrorCode.RATE_LIMITED.value, str(exc), provider=provider, details=exc.payload)
            if status and status >= 500:
                return ProviderRuntimeError(ProviderErrorCode.TEMPORARY_UNAVAILABLE.value, str(exc), provider=provider, details=exc.payload)
            return ProviderRuntimeError(ProviderErrorCode.TRANSPORT_ERROR.value, str(exc), provider=provider, details=exc.payload)
        return ProviderRuntimeError(ProviderErrorCode.TRANSPORT_ERROR.value, str(exc), provider=provider)

    def _build_headers(self, *, auth: ProviderAuthContract, request_contract: ProviderRequestContract) -> dict[str, str]:
        headers = dict(request_contract.default_headers or {})
        if request_contract.stable_version_header_name and request_contract.stable_version_header_value:
            headers[request_contract.stable_version_header_name] = request_contract.stable_version_header_value
        if auth.auth_kind == ProviderAuthKind.NONE:
            return headers
        if auth.auth_kind == ProviderAuthKind.API_KEY_HEADER:
            secret = self.secrets.read(auth.secret_ref_primary)
            if not secret:
                raise ProviderRuntimeError(ProviderErrorCode.AUTH_REQUIRED.value, 'missing provider api key', provider=auth.provider)
            header_name = _text(auth.header_name, default='Authorization')
            template = _text(auth.header_value_template, default='{secret}')
            headers[header_name] = template.format(secret=secret)
            return headers
        if auth.auth_kind == ProviderAuthKind.BEARER_TOKEN:
            token = self.secrets.read(auth.secret_ref_primary)
            if not token:
                raise ProviderRuntimeError(ProviderErrorCode.AUTH_REQUIRED.value, 'missing provider bearer token', provider=auth.provider)
            header_name = _text(auth.header_name, default='Authorization')
            template = _text(auth.header_value_template, default='Bearer {secret}')
            headers[header_name] = template.format(secret=token)
            return headers
        if auth.auth_kind == ProviderAuthKind.BASIC:
            username = self.secrets.read(auth.basic_username_ref)
            password = self.secrets.read(auth.basic_password_ref)
            if not username or not password:
                raise ProviderRuntimeError(ProviderErrorCode.AUTH_REQUIRED.value, 'missing provider basic auth credentials', provider=auth.provider)
            raw = f'{username}:{password}'.encode()
            headers['Authorization'] = f"Basic {base64.b64encode(raw).decode('ascii')}"
            return headers
        return headers

    def _build_query_params(self, *, payload: Mapping[str, Any], request_contract: ProviderRequestContract, auth: ProviderAuthContract) -> dict[str, Any]:
        params: dict[str, Any] = {}
        allowed = set(request_contract.allowed_query_keys)
        required = set(request_contract.required_query_keys)
        for key in allowed:
            if payload.get(key) is not None:
                params[key] = payload.get(key)
        for key in required:
            if payload.get(key) in {None, ''}:
                raise ProviderRuntimeError(
                    ProviderErrorCode.CONTRACT_VIOLATION.value,
                    f'missing required query key: {key}',
                    provider=request_contract.provider,
                    details={'operation': request_contract.operation},
                )
        if auth.auth_kind == ProviderAuthKind.API_KEY_QUERY:
            secret = self.secrets.read(auth.secret_ref_primary)
            if not secret:
                raise ProviderRuntimeError(ProviderErrorCode.AUTH_REQUIRED.value, 'missing provider query api key', provider=request_contract.provider)
            params[_text(auth.query_param_name, default='api_key')] = secret
        return params

    def _build_body(self, *, payload: Mapping[str, Any], request_contract: ProviderRequestContract) -> dict[str, Any] | None:
        if request_contract.method not in {'POST', 'PUT', 'PATCH'}:
            return None
        body: dict[str, Any] = {}
        allowed = set(request_contract.allowed_body_keys)
        required = set(request_contract.required_body_keys)
        for key in allowed:
            if payload.get(key) is not None:
                body[key] = payload.get(key)
        for key in required:
            if body.get(key) in {None, ''}:
                raise ProviderRuntimeError(
                    ProviderErrorCode.CONTRACT_VIOLATION.value,
                    f'missing required body key: {key}',
                    provider=request_contract.provider,
                    details={'operation': request_contract.operation},
                )
        return body

    def _validate_payload(self, *, payload: Mapping[str, Any], schema: ProviderSchemaContract, request_contract: ProviderRequestContract) -> None:
        for field_name in schema.input_required_fields:
            if payload.get(field_name) in {None, ''}:
                raise ProviderRuntimeError(
                    ProviderErrorCode.CONTRACT_VIOLATION.value,
                    f'missing required input field: {field_name}',
                    provider=request_contract.provider,
                    details={'operation': request_contract.operation},
                )

    def _bootstrap_defaults(self) -> None:
        for alias, provider in PROVIDER_ALIASES.items():
            self.registry.register_alias(alias, provider)

        for provider_key, entry in PROVIDER_CATALOG.items():
            manifest = ProviderCapabilityManifest(
                provider=entry.provider,
                source_family=entry.source_family,
                supported_operations=operations_for_family(entry.source_family),
                compliance_classification=entry.compliance_classification,
                robots_sensitive=entry.robots_sensitive,
                terms_sensitive=entry.terms_sensitive,
                supports_rate_limit_headers=entry.supports_rate_limit_headers,
                metadata=dict(entry.metadata or {}),
            )
            self.registry.register_manifest(manifest)
            auth = ProviderAuthContract(
                provider=entry.provider,
                auth_kind=entry.auth_kind,
                secret_ref_primary=entry.secret_ref_primary,
                secret_ref_secondary=entry.secret_ref_secondary,
                query_param_name=entry.query_param_name,
                header_name=entry.header_name,
                header_value_template=entry.header_value_template,
                basic_username_ref=entry.basic_username_ref,
                basic_password_ref=entry.basic_password_ref,
            )
            self.registry.register_auth_contract(auth)
            for operation in operations_for_family(entry.source_family):
                request_contract = self._build_request_contract(entry=entry, operation=operation)
                schema_contract = self._build_schema_contract(entry=entry, operation=operation)
                self.registry.register_request_contract(request_contract)
                self.registry.register_schema_contract(schema_contract)

    def _build_request_contract(self, *, entry, operation: str) -> ProviderRequestContract:
        query_keys = self._allowed_query_keys(entry.source_family, operation)
        required_keys = self._required_query_keys(entry.source_family, operation)
        return ProviderRequestContract(
            provider=entry.provider,
            source_family=entry.source_family,
            operation=operation,
            method='GET',
            base_url=_text(os.getenv(entry.env_base_url_key), default=entry.default_base_url),
            path=f'/{entry.source_family}/{entry.provider}/{operation}',
            allowed_query_keys=query_keys,
            required_query_keys=required_keys,
            stable_version_header_name=entry.stable_version_header_name,
            stable_version_header_value=entry.stable_version_header_value,
        )

    def _build_schema_contract(self, *, entry, operation: str) -> ProviderSchemaContract:
        return ProviderSchemaContract(
            provider=entry.provider,
            source_family=entry.source_family,
            operation=operation,
            input_required_fields=self._required_input_fields(entry.source_family, operation),
            output_required_fields=('external_id', 'title'),
        )

    def _allowed_query_keys(self, source_family: str, operation: str) -> tuple[str, ...]:
        common = ('query', 'subject_url', 'account_ref', 'region', 'locale', 'limit', 'page_limit', 'cursor')
        if source_family in {'landing_intelligence', 'competitor_analytics'}:
            return ('subject_url', 'query', 'region', 'locale', 'limit', 'page_limit', 'cursor')
        if source_family in {'app_store', 'marketplace', 'ads_library', 'search_intelligence', 'professional_network', 'content_platform', 'review_platform', 'video_platform', 'ads_spy', 'newsletter_intelligence'}:
            return common
        return common

    def _required_query_keys(self, source_family: str, operation: str) -> tuple[str, ...]:
        if source_family in {'landing_intelligence', 'competitor_analytics'}:
            return ('subject_url',)
        return ('query',)

    def _required_input_fields(self, source_family: str, operation: str) -> tuple[str, ...]:
        return self._required_query_keys(source_family, operation)


__all__ = [
    'CANON_MARKET_INTELLIGENCE_PROVIDER_RUNTIME',
    'ProviderRequestPlanV2',
    'ProviderRuntimeError',
    'ProviderRuntimeFactory',
    'SecretReader',
]
