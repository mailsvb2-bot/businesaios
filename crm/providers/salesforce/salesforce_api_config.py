from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

_API_VERSION_RE = re.compile(r'^v\d+\.\d+$')


@dataclass(frozen=True)
class SalesforceApiConfig:
    api_version: str = 'v67.0'
    timeout_seconds: float = 20.0
    allowed_instance_host_suffixes: tuple[str, ...] = ('.salesforce.com',)

    def __post_init__(self) -> None:
        if not _API_VERSION_RE.fullmatch(self.api_version):
            raise ValueError('Salesforce api_version must look like v67.0')
        if self.timeout_seconds <= 0:
            raise ValueError('Salesforce timeout_seconds must be positive')
        if not self.allowed_instance_host_suffixes:
            raise ValueError('Salesforce allowed instance host suffixes must not be empty')
        if any(not suffix.startswith('.') or '/' in suffix for suffix in self.allowed_instance_host_suffixes):
            raise ValueError('Salesforce allowed instance host suffixes must look like .salesforce.com')

    def rest_base(self, instance_url: str) -> str:
        parsed = urlsplit(instance_url.strip())
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https':
            raise ValueError('Salesforce instance_url must use HTTPS')
        if not host or not any(host.endswith(suffix) for suffix in self.allowed_instance_host_suffixes):
            raise ValueError('Salesforce instance_url host is not an allowed Salesforce API host')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Salesforce instance_url must not contain credentials, query, or fragment')
        if parsed.path not in ('', '/'):
            raise ValueError('Salesforce instance_url must not contain an API path')
        if parsed.port not in (None, 443):
            raise ValueError('Salesforce instance_url must use the standard HTTPS port')
        authority = host if parsed.port is None else f'{host}:{parsed.port}'
        return f'https://{authority}/services/data/{self.api_version}'
