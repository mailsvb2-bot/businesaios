from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from security.pii_redaction_policy import PIIRedactionPolicy


CANON_PAYLOAD_REDACTION = True


class PayloadRedactor:
    DEFAULT_SECRET_KEYS = (
        'secret', 'token', 'password', 'passwd', 'key', 'authorization',
        'cookie', 'set-cookie', 'signature', 'api_key', 'access_token', 'refresh_token',
        'private_key', 'client_secret', 'bearer',
    )

    def __init__(
        self,
        *,
        pii_policy: PIIRedactionPolicy | None = None,
        secret_replacement: str = '***REDACTED***',
        max_string_length: int = 2048,
        sensitive_keys: tuple[str, ...] | None = None,
        max_depth: int = 12,
    ) -> None:
        self._pii_policy = pii_policy or PIIRedactionPolicy()
        self._secret_replacement = str(secret_replacement)
        self._max_string_length = int(max_string_length)
        self._sensitive_keys = tuple((sensitive_keys or self.DEFAULT_SECRET_KEYS))
        self._max_depth = int(max_depth)

    def redact(self, payload: Any) -> Any:
        normalized = self._normalize(payload)
        return self._redact_value(key_hint=None, value=normalized, depth=0)

    def _normalize(self, value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        return value

    def _redact_value(self, *, key_hint: str | None, value: Any, depth: int) -> Any:
        if depth > self._max_depth:
            return '<max-depth-redacted>'
        if isinstance(value, Mapping):
            return {str(k): self._redact_value(key_hint=str(k), value=v, depth=depth + 1) for k, v in value.items()}
        if isinstance(value, tuple):
            return tuple(self._redact_value(key_hint=key_hint, value=item, depth=depth + 1) for item in value)
        if isinstance(value, list):
            return [self._redact_value(key_hint=key_hint, value=item, depth=depth + 1) for item in value]
        if isinstance(value, (set, frozenset)):
            return sorted(self._redact_value(key_hint=key_hint, value=item, depth=depth + 1) for item in value)
        if isinstance(value, bytes):
            return self._redact_scalar(key_hint=key_hint, value=value.decode('utf-8', errors='replace'))
        return self._redact_scalar(key_hint=key_hint, value=value)

    def _redact_scalar(self, *, key_hint: str | None, value: Any) -> Any:
        if key_hint and self._is_sensitive_key(key_hint):
            return self._secret_replacement
        if isinstance(value, str):
            text = self._pii_policy.redact_text(value)
            if len(text) > self._max_string_length:
                return text[: self._max_string_length] + '…'
            return text
        return value

    def _is_sensitive_key(self, key_hint: str) -> bool:
        normalized = str(key_hint or '').strip().lower()
        return any(token in normalized for token in self._sensitive_keys)


__all__ = [
    'CANON_PAYLOAD_REDACTION',
    'PayloadRedactor',
]
