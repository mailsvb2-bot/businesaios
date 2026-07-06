from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from security.secret_contract import SecretRef

CANON_COMPAT_SHIM = True

CANON_SECRETS_RESOLUTION_POLICY = True

_SECRET_REF_PREFIX = "secret://"
_SENSITIVE_KEY_MARKERS = ("secret", "token", "password", "apikey", "api_key", "private_key", "credential")


class SecretResolver(Protocol):
    def get(self, ref: SecretRef) -> bytes: ...


@dataclass(frozen=True)
class SecretResolutionRequest:
    tenant_id: str
    config_key: str
    secret_uri: str
    connector_id: str | None = None
    scope: str | None = None
    version: str = "current"

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.config_key or "").strip():
            raise ValueError("config_key is required")
        if not str(self.secret_uri or "").strip().startswith(_SECRET_REF_PREFIX):
            raise ValueError("secret_uri must start with secret://")
        if not str(self.version or "").strip():
            raise ValueError("version is required")

    def to_secret_ref(self) -> SecretRef:
        self.validate()
        raw_uri = self.secret_uri.strip()
        remainder = raw_uri[len(_SECRET_REF_PREFIX):]
        secret_part, _, query = remainder.partition("?")
        secret_name = secret_part.strip("/")
        if not secret_name:
            raise ValueError("secret name is required")
        version = str(self.version).strip() or "current"
        if query:
            for part in query.split("&"):
                key, _, value = part.partition("=")
                if key.strip() == "version" and value.strip():
                    version = value.strip()
                    break
        ref = SecretRef(
            tenant_id=str(self.tenant_id).strip(),
            connector_id=None if self.connector_id is None else str(self.connector_id).strip() or None,
            scope=None if self.scope is None else str(self.scope).strip() or None,
            secret_name=secret_name,
            version=version,
        )
        ref.validate()
        return ref


@dataclass(frozen=True)
class SecretsResolutionPolicy:
    allow_plaintext_keys: tuple[str, ...] = field(default_factory=tuple)
    required_secret_keys: tuple[str, ...] = field(default_factory=tuple)
    redact_token: str = "[REDACTED]"

    def _normalized_allow_plaintext_keys(self) -> set[str]:
        return {str(item).strip().lower() for item in self.allow_plaintext_keys if str(item).strip()}

    def validate_mapping(self, payload: Mapping[str, object]) -> None:
        rows = dict(payload or {})
        for key in self.required_secret_keys:
            text_key = str(key).strip()
            if not text_key:
                raise ValueError("required_secret_keys must not contain empty values")
            value = rows.get(text_key)
            if not isinstance(value, str) or not value.strip().startswith(_SECRET_REF_PREFIX):
                raise ValueError(f"{text_key} must be configured as a secret:// reference")

    def resolve_mapping(
        self,
        payload: Mapping[str, object],
        *,
        tenant_id: str,
        resolver: SecretResolver,
        connector_id: str | None = None,
        scope: str | None = None,
    ) -> dict[str, object]:
        self.validate_mapping(payload)
        return {
            str(key): self._resolve_value(
                value,
                tenant_id=str(tenant_id).strip(),
                config_key=str(key),
                resolver=resolver,
                connector_id=connector_id,
                scope=scope,
            )
            for key, value in dict(payload or {}).items()
        }

    def redact_mapping(self, payload: Mapping[str, object]) -> dict[str, object]:
        return {str(key): self._redact_value(key=str(key), value=value) for key, value in dict(payload or {}).items()}

    def _resolve_value(
        self,
        value: object,
        *,
        tenant_id: str,
        config_key: str,
        resolver: SecretResolver,
        connector_id: str | None,
        scope: str | None,
    ) -> object:
        if isinstance(value, str) and value.strip().startswith(_SECRET_REF_PREFIX):
            request = SecretResolutionRequest(
                tenant_id=tenant_id,
                config_key=config_key,
                secret_uri=value.strip(),
                connector_id=connector_id,
                scope=scope,
            )
            return resolver.get(request.to_secret_ref()).decode("utf-8")
        if isinstance(value, Mapping):
            return {
                str(child_key): self._resolve_value(
                    child_value,
                    tenant_id=tenant_id,
                    config_key=f"{config_key}.{child_key}",
                    resolver=resolver,
                    connector_id=connector_id,
                    scope=scope,
                )
                for child_key, child_value in dict(value).items()
            }
        if isinstance(value, list | tuple):
            resolved_items = [
                self._resolve_value(
                    item,
                    tenant_id=tenant_id,
                    config_key=f"{config_key}[{index}]",
                    resolver=resolver,
                    connector_id=connector_id,
                    scope=scope,
                )
                for index, item in enumerate(value)
            ]
            return resolved_items if isinstance(value, list) else tuple(resolved_items)
        return value

    def _redact_value(self, *, key: str, value: object) -> object:
        if isinstance(value, str) and value.strip().startswith(_SECRET_REF_PREFIX):
            return value.strip()
        if isinstance(value, Mapping):
            return {str(child_key): self._redact_value(key=f"{key}.{child_key}", value=child_value) for child_key, child_value in dict(value).items()}
        if isinstance(value, list | tuple):
            redacted = [self._redact_value(key=f"{key}[]", value=item) for item in value]
            return redacted if isinstance(value, list) else tuple(redacted)
        normalized_key = str(key or "").strip().lower()
        if normalized_key in self._normalized_allow_plaintext_keys():
            return value
        if any(marker in normalized_key for marker in _SENSITIVE_KEY_MARKERS):
            return self.redact_token
        return value


__all__ = [
    "CANON_SECRETS_RESOLUTION_POLICY",
    "SecretResolutionRequest",
    "SecretResolver",
    "SecretsResolutionPolicy",
]
