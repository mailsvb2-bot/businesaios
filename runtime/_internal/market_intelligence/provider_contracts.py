from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

CANON_MARKET_INTELLIGENCE_PROVIDER_CONTRACTS = True


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def _tuple_text(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        out = [str(item).strip() for item in value if str(item).strip()]
        return tuple(out)
    text = _text(value)
    return (text,) if text else ()


def _dict_str_any(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


class ProviderAuthKind(str, Enum):
    NONE = 'none'
    API_KEY_HEADER = 'api_key_header'
    API_KEY_QUERY = 'api_key_query'
    BEARER_TOKEN = 'bearer_token'
    BASIC = 'basic'


class ProviderErrorCode(str, Enum):
    AUTH_REQUIRED = 'auth_required'
    AUTH_INVALID = 'auth_invalid'
    FORBIDDEN = 'forbidden'
    NOT_FOUND = 'not_found'
    RATE_LIMITED = 'rate_limited'
    VERSION_MISMATCH = 'version_mismatch'
    CONTRACT_VIOLATION = 'contract_violation'
    INVALID_RESPONSE = 'invalid_response'
    TEMPORARY_UNAVAILABLE = 'temporary_unavailable'
    TRANSPORT_ERROR = 'transport_error'
    POISONED_SOURCE = 'poisoned_source'
    QUARANTINED_SOURCE = 'quarantined_source'


@dataclass(frozen=True)
class ProviderCapabilityManifest:
    provider: str
    source_family: str
    supported_operations: tuple[str, ...]
    supports_incremental_sync: bool = True
    supports_cursoring: bool = True
    supports_backfill: bool = True
    supports_rate_limit_headers: bool = True
    supports_retry_after: bool = True
    supports_entity_identity: bool = True
    compliance_classification: str = 'public_web'
    robots_sensitive: bool = False
    terms_sensitive: bool = False
    version: str = 'v1'
    input_schema_version: str = 'v1'
    output_schema_version: str = 'v1'
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'provider', _text(self.provider))
        object.__setattr__(self, 'source_family', _text(self.source_family))
        object.__setattr__(self, 'supported_operations', _tuple_text(self.supported_operations))
        object.__setattr__(self, 'compliance_classification', _text(self.compliance_classification, default='public_web'))
        object.__setattr__(self, 'version', _text(self.version, default='v1'))
        object.__setattr__(self, 'input_schema_version', _text(self.input_schema_version, default='v1'))
        object.__setattr__(self, 'output_schema_version', _text(self.output_schema_version, default='v1'))
        object.__setattr__(self, 'metadata', _dict_str_any(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            'provider': self.provider,
            'source_family': self.source_family,
            'supported_operations': list(self.supported_operations),
            'supports_incremental_sync': self.supports_incremental_sync,
            'supports_cursoring': self.supports_cursoring,
            'supports_backfill': self.supports_backfill,
            'supports_rate_limit_headers': self.supports_rate_limit_headers,
            'supports_retry_after': self.supports_retry_after,
            'supports_entity_identity': self.supports_entity_identity,
            'compliance_classification': self.compliance_classification,
            'robots_sensitive': self.robots_sensitive,
            'terms_sensitive': self.terms_sensitive,
            'version': self.version,
            'input_schema_version': self.input_schema_version,
            'output_schema_version': self.output_schema_version,
            'metadata': dict(self.metadata),
        }


@dataclass(frozen=True)
class ProviderSchemaContract:
    provider: str
    source_family: str
    operation: str
    input_required_fields: tuple[str, ...]
    output_required_fields: tuple[str, ...]
    output_identity_field: str = 'external_id'
    version: str = 'v1'

    def __post_init__(self) -> None:
        object.__setattr__(self, 'provider', _text(self.provider))
        object.__setattr__(self, 'source_family', _text(self.source_family))
        object.__setattr__(self, 'operation', _text(self.operation))
        object.__setattr__(self, 'input_required_fields', _tuple_text(self.input_required_fields))
        object.__setattr__(self, 'output_required_fields', _tuple_text(self.output_required_fields))
        object.__setattr__(self, 'output_identity_field', _text(self.output_identity_field, default='external_id'))
        object.__setattr__(self, 'version', _text(self.version, default='v1'))


@dataclass(frozen=True)
class ProviderAuthContract:
    provider: str
    auth_kind: ProviderAuthKind = ProviderAuthKind.NONE
    secret_ref_primary: str | None = None
    secret_ref_secondary: str | None = None
    query_param_name: str | None = None
    header_name: str | None = None
    header_value_template: str | None = None
    basic_username_ref: str | None = None
    basic_password_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'provider', _text(self.provider))
        object.__setattr__(self, 'secret_ref_primary', _text(self.secret_ref_primary) or None)
        object.__setattr__(self, 'secret_ref_secondary', _text(self.secret_ref_secondary) or None)
        object.__setattr__(self, 'query_param_name', _text(self.query_param_name) or None)
        object.__setattr__(self, 'header_name', _text(self.header_name) or None)
        object.__setattr__(self, 'header_value_template', _text(self.header_value_template) or None)
        object.__setattr__(self, 'basic_username_ref', _text(self.basic_username_ref) or None)
        object.__setattr__(self, 'basic_password_ref', _text(self.basic_password_ref) or None)


@dataclass(frozen=True)
class ProviderRequestContract:
    provider: str
    source_family: str
    operation: str
    method: str
    base_url: str
    path: str
    page_size_param: str = 'limit'
    cursor_param: str = 'cursor'
    item_path: str = 'items'
    next_cursor_path: str = 'next_cursor'
    default_headers: Mapping[str, str] = field(default_factory=dict)
    allowed_query_keys: tuple[str, ...] = field(default_factory=tuple)
    required_query_keys: tuple[str, ...] = field(default_factory=tuple)
    allowed_body_keys: tuple[str, ...] = field(default_factory=tuple)
    required_body_keys: tuple[str, ...] = field(default_factory=tuple)
    stable_version_header_name: str | None = None
    stable_version_header_value: str | None = None
    version: str = 'v1'

    def __post_init__(self) -> None:
        object.__setattr__(self, 'provider', _text(self.provider))
        object.__setattr__(self, 'source_family', _text(self.source_family))
        object.__setattr__(self, 'operation', _text(self.operation))
        object.__setattr__(self, 'method', _text(self.method, default='GET').upper())
        object.__setattr__(self, 'base_url', _text(self.base_url))
        object.__setattr__(self, 'path', _text(self.path))
        object.__setattr__(self, 'page_size_param', _text(self.page_size_param, default='limit'))
        object.__setattr__(self, 'cursor_param', _text(self.cursor_param, default='cursor'))
        object.__setattr__(self, 'item_path', _text(self.item_path, default='items'))
        object.__setattr__(self, 'next_cursor_path', _text(self.next_cursor_path, default='next_cursor'))
        object.__setattr__(self, 'default_headers', {str(k): str(v) for k, v in dict(self.default_headers or {}).items()})
        object.__setattr__(self, 'allowed_query_keys', _tuple_text(self.allowed_query_keys))
        object.__setattr__(self, 'required_query_keys', _tuple_text(self.required_query_keys))
        object.__setattr__(self, 'allowed_body_keys', _tuple_text(self.allowed_body_keys))
        object.__setattr__(self, 'required_body_keys', _tuple_text(self.required_body_keys))
        object.__setattr__(self, 'stable_version_header_name', _text(self.stable_version_header_name) or None)
        object.__setattr__(self, 'stable_version_header_value', _text(self.stable_version_header_value) or None)
        object.__setattr__(self, 'version', _text(self.version, default='v1'))


class ProviderContractRegistry:
    def __init__(self) -> None:
        self._manifests: dict[str, ProviderCapabilityManifest] = {}
        self._request_contracts: dict[tuple[str, str], ProviderRequestContract] = {}
        self._schema_contracts: dict[tuple[str, str], ProviderSchemaContract] = {}
        self._auth_contracts: dict[str, ProviderAuthContract] = {}
        self._aliases: dict[str, str] = {}

    def register_alias(self, alias: str, provider: str) -> None:
        alias_text = _text(alias).lower()
        provider_text = _text(provider).lower()
        if not alias_text:
            raise ValueError('alias is required')
        if not provider_text:
            raise ValueError('provider is required')
        self._aliases[alias_text] = provider_text

    def canonical_provider(self, provider: str) -> str:
        key = _text(provider).lower()
        return self._aliases.get(key, key)

    def is_explicit_alias(self, provider: str) -> bool:
        return _text(provider).lower() in self._aliases

    def register_manifest(self, manifest: ProviderCapabilityManifest) -> None:
        self._manifests[self.canonical_provider(manifest.provider)] = manifest

    def register_request_contract(self, contract: ProviderRequestContract) -> None:
        self._request_contracts[(self.canonical_provider(contract.provider), contract.operation)] = contract

    def register_schema_contract(self, contract: ProviderSchemaContract) -> None:
        self._schema_contracts[(self.canonical_provider(contract.provider), contract.operation)] = contract

    def register_auth_contract(self, contract: ProviderAuthContract) -> None:
        self._auth_contracts[self.canonical_provider(contract.provider)] = contract

    def manifest(self, provider: str) -> ProviderCapabilityManifest:
        manifest = self._manifests.get(self.canonical_provider(provider))
        if manifest is None:
            raise KeyError(f'provider manifest not registered: {provider}')
        return manifest

    def request_contract(self, provider: str, operation: str) -> ProviderRequestContract:
        contract = self._request_contracts.get((self.canonical_provider(provider), _text(operation)))
        if contract is None:
            raise KeyError(f'provider request contract not registered: {provider}/{operation}')
        return contract

    def schema_contract(self, provider: str, operation: str) -> ProviderSchemaContract:
        contract = self._schema_contracts.get((self.canonical_provider(provider), _text(operation)))
        if contract is None:
            raise KeyError(f'provider schema contract not registered: {provider}/{operation}')
        return contract

    def auth_contract(self, provider: str) -> ProviderAuthContract:
        canonical = self.canonical_provider(provider)
        return self._auth_contracts.get(canonical, ProviderAuthContract(provider=canonical))

    def validate_no_hidden_fallback(self, *, requested_provider: str, resolved_provider: str) -> None:
        requested = _text(requested_provider).lower()
        resolved = _text(resolved_provider).lower()
        canonical_requested = self.canonical_provider(requested)
        canonical_resolved = self.canonical_provider(resolved)
        if requested == resolved:
            return
        if self.is_explicit_alias(requested) and self._aliases[requested] == canonical_resolved:
            return
        if canonical_requested == canonical_resolved and requested == canonical_requested:
            return
        raise ValueError(f'hidden fallback path is forbidden: requested={requested!r} resolved={resolved!r}')

    def snapshot(self) -> dict[str, Any]:
        return {
            'providers': {key: value.as_dict() for key, value in self._manifests.items()},
            'aliases': dict(self._aliases),
            'request_contracts': sorted(f'{provider}:{op}' for provider, op in self._request_contracts.keys()),
            'schema_contracts': sorted(f'{provider}:{op}' for provider, op in self._schema_contracts.keys()),
            'auth_contracts': sorted(self._auth_contracts.keys()),
        }


__all__ = [
    'CANON_MARKET_INTELLIGENCE_PROVIDER_CONTRACTS',
    'ProviderAuthContract',
    'ProviderAuthKind',
    'ProviderCapabilityManifest',
    'ProviderContractRegistry',
    'ProviderErrorCode',
    'ProviderRequestContract',
    'ProviderSchemaContract',
]
