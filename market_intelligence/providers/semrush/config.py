from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SemrushConfig:
    api_key: str
    base_url_v3: str = 'https://api.semrush.com/'
    timeout_seconds: float = 15.0
    allowed_api_hosts: tuple[str, ...] = ('api.semrush.com',)

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError('Semrush API key is required')
        if self.timeout_seconds <= 0:
            raise ValueError('Semrush timeout_seconds must be positive')
        parsed = urlsplit(self.base_url_v3.strip())
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https':
            raise ValueError('Semrush base URL must use HTTPS')
        if host not in {item.lower() for item in self.allowed_api_hosts}:
            raise ValueError('Semrush base URL host is not in allowed_api_hosts')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Semrush base URL must not contain credentials, query, or fragment')
        if parsed.port not in (None, 443):
            raise ValueError('Semrush base URL must use the standard HTTPS port')

    def safe_dict(self) -> dict[str, object]:
        return {
            'base_url_v3': self.base_url_v3,
            'timeout_seconds': self.timeout_seconds,
            'api_key': '<redacted>',
        }
