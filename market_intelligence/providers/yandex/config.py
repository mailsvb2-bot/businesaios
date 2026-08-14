from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


_WORDSTAT_HOST = 'api.wordstat.yandex.net'
_WEBMASTER_HOST = 'api.webmaster.yandex.net'
_ALLOWED_DEVICES = frozenset({'all', 'desktop', 'phone', 'tablet'})
_ALLOWED_WEBMASTER_DEVICES = frozenset({'ALL', 'DESKTOP', 'MOBILE_AND_TABLET', 'MOBILE', 'TABLET'})
_ALLOWED_ORDER_FIELDS = frozenset({'TOTAL_SHOWS', 'TOTAL_CLICKS'})


def _validated_https_base(url: str, *, expected_host: str) -> str:
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or '').casefold()
    if parsed.scheme != 'https' or host != expected_host:
        raise ValueError(f'provider base URL must use https://{expected_host}')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('provider base URL must not contain credentials, query, or fragment')
    if parsed.path not in ('', '/') or parsed.port not in (None, 443):
        raise ValueError('provider base URL must not contain a path or non-standard port')
    return f'https://{expected_host}'


@dataclass(frozen=True)
class WordstatConfig:
    oauth_token: str
    regions: tuple[int, ...] = ()
    devices: tuple[str, ...] = ('all',)
    base_url: str = 'https://api.wordstat.yandex.net'
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not self.oauth_token.strip():
            raise ValueError('Wordstat OAuth token must not be blank')
        if self.timeout_seconds <= 0:
            raise ValueError('Wordstat timeout_seconds must be positive')
        if any(not isinstance(region, int) or region < 0 for region in self.regions):
            raise ValueError('Wordstat regions must contain non-negative integer IDs')
        normalized_devices = tuple(device.strip().casefold() for device in self.devices)
        if not normalized_devices or any(device not in _ALLOWED_DEVICES for device in normalized_devices):
            raise ValueError('Wordstat devices contain an unsupported value')
        object.__setattr__(self, 'devices', normalized_devices)
        object.__setattr__(self, 'base_url', _validated_https_base(self.base_url, expected_host=_WORDSTAT_HOST))


@dataclass(frozen=True)
class WebmasterConfig:
    oauth_token: str
    user_id: int
    host_id: str
    device_type: str = 'ALL'
    order_by: str = 'TOTAL_SHOWS'
    base_url: str = 'https://api.webmaster.yandex.net'
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not self.oauth_token.strip():
            raise ValueError('Webmaster OAuth token must not be blank')
        if not isinstance(self.user_id, int) or self.user_id <= 0:
            raise ValueError('Webmaster user_id must be a positive integer')
        if not self.host_id.strip():
            raise ValueError('Webmaster host_id must not be blank')
        if self.timeout_seconds <= 0:
            raise ValueError('Webmaster timeout_seconds must be positive')
        device_type = self.device_type.strip().upper()
        order_by = self.order_by.strip().upper()
        if device_type not in _ALLOWED_WEBMASTER_DEVICES:
            raise ValueError('Webmaster device_type is unsupported')
        if order_by not in _ALLOWED_ORDER_FIELDS:
            raise ValueError('Webmaster order_by is unsupported')
        object.__setattr__(self, 'device_type', device_type)
        object.__setattr__(self, 'order_by', order_by)
        object.__setattr__(self, 'base_url', _validated_https_base(self.base_url, expected_host=_WEBMASTER_HOST))
