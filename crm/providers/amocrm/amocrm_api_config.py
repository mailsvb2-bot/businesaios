from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AmoCrmApiConfig:
    timeout_seconds: float = 20.0
    allowed_account_host_suffixes: tuple[str, ...] = ('.amocrm.ru',)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError('amoCRM timeout_seconds must be positive')
        if not self.allowed_account_host_suffixes:
            raise ValueError('amoCRM allowed host suffixes must not be empty')
        if any(not suffix.startswith('.') or '/' in suffix for suffix in self.allowed_account_host_suffixes):
            raise ValueError('amoCRM allowed host suffixes are malformed')

    def account_base(self, value: str) -> str:
        raw = value.strip()
        if not raw:
            raise ValueError('amoCRM account address must not be blank')
        if '://' not in raw:
            raw = f'https://{raw}'
        parsed = urlsplit(raw)
        host = (parsed.hostname or '').casefold()
        if parsed.scheme != 'https':
            raise ValueError('amoCRM account address must use HTTPS')
        if not host or not any(host.endswith(suffix) for suffix in self.allowed_account_host_suffixes):
            raise ValueError('amoCRM account host is not allowed')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('amoCRM account address must not contain credentials, query, or fragment')
        if parsed.path not in ('', '/') or parsed.port not in (None, 443):
            raise ValueError('amoCRM account address must not contain an API path or non-standard port')
        return f'https://{host}'
