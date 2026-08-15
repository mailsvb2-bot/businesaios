from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Bitrix24ApiConfig:
    timeout_seconds: float = 20.0
    oauth_token_url: str = 'https://oauth.bitrix.info/oauth/token/'
    trusted_cloud_suffixes: tuple[str, ...] = (
        '.bitrix24.com.br',
        '.bitrix24.com',
        '.bitrix24.eu',
        '.bitrix24.de',
        '.bitrix24.es',
        '.bitrix24.in',
        '.bitrix24.cn',
        '.bitrix24.fr',
        '.bitrix24.pl',
        '.bitrix24.tr',
        '.bitrix24.uk',
        '.bitrix24.co',
        '.bitrix24.mx',
        '.bitrix24.ru',
    )
    trusted_portal_hosts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError('Bitrix24 timeout_seconds must be positive')
        oauth = urlsplit(self.oauth_token_url)
        if oauth.scheme != 'https' or oauth.hostname != 'oauth.bitrix.info':
            raise ValueError('Bitrix24 OAuth endpoint must use oauth.bitrix.info over HTTPS')
        if any(not suffix.startswith('.') or '/' in suffix for suffix in self.trusted_cloud_suffixes):
            raise ValueError('Bitrix24 trusted cloud suffix is malformed')
        if any('/' in host or '://' in host for host in self.trusted_portal_hosts):
            raise ValueError('Bitrix24 trusted portal host must be a hostname')

    def portal_rest_base(self, client_endpoint: str) -> str:
        parsed = urlsplit(str(client_endpoint or '').strip())
        host = (parsed.hostname or '').casefold()
        trusted_exact = {value.casefold() for value in self.trusted_portal_hosts}
        trusted_suffix = any(host.endswith(suffix.casefold()) for suffix in self.trusted_cloud_suffixes)
        if parsed.scheme != 'https' or not host:
            raise ValueError('Bitrix24 client endpoint must use HTTPS')
        if not trusted_suffix and host not in trusted_exact:
            raise ValueError('Bitrix24 portal host is not trusted')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Bitrix24 client endpoint must not contain credentials, query, or fragment')
        if parsed.port not in (None, 443):
            raise ValueError('Bitrix24 client endpoint must not use a non-standard port')
        normalized_path = parsed.path.rstrip('/')
        if normalized_path != '/rest':
            raise ValueError('Bitrix24 client endpoint must point to the REST root')
        return f'https://{host}/rest'
