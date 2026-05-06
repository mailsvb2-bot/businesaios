from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import json
import random
import time
from typing import Any, Iterable, Mapping
from urllib import error, parse, request


CANON_MARKET_INTELLIGENCE_HTTP_TRANSPORT = True


class HttpTransportError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None, payload: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = str(code or 'transport_error')
        self.status_code = None if status_code is None else int(status_code)
        self.payload = dict(payload or {})


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    params: Mapping[str, Any] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    body: Mapping[str, Any] | None = None
    timeout_seconds: float = 20.0
    accept_json: bool = True

    def build_url(self) -> str:
        pairs: list[tuple[str, Any]] = []
        for key, value in dict(self.params or {}).items():
            if value is None:
                continue
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray, Mapping)):
                for item in value:
                    if item is not None:
                        pairs.append((str(key), str(item)))
            else:
                pairs.append((str(key), str(value)))
        query = parse.urlencode(pairs, doseq=True)
        return f'{self.url}?{query}' if query else self.url


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    text: str
    json_payload: Any = None
    requested_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    retryable_statuses: tuple[int, ...] = (408, 409, 425, 429, 500, 502, 503, 504)

    def should_retry(self, *, attempt: int, status_code: int | None, code: str) -> bool:
        if int(attempt) >= int(self.max_attempts):
            return False
        if status_code is not None and int(status_code) in set(self.retryable_statuses):
            return True
        return str(code) in {'timeout', 'transport_error', 'temporary_unavailable', 'temporarily_unavailable', 'rate_limited'}

    def sleep_seconds(self, *, attempt: int, retry_after_seconds: float | None = None) -> float:
        if retry_after_seconds is not None and retry_after_seconds > 0:
            return min(float(retry_after_seconds), float(self.max_delay_seconds))
        base = min(float(self.base_delay_seconds) * (2 ** max(0, int(attempt) - 1)), float(self.max_delay_seconds))
        jitter = random.uniform(0.0, min(base / 3.0, 1.0))
        return min(base + jitter, float(self.max_delay_seconds))


@dataclass
class RateLimitState:
    reset_at: float | None = None
    retry_after_seconds: float | None = None

    def is_blocked(self) -> bool:
        if self.reset_at is None:
            return False
        return time.time() < float(self.reset_at)


class CanonicalHttpTransport:
    def __init__(self, *, retry_policy: RetryPolicy | None = None) -> None:
        self._retry_policy = retry_policy or RetryPolicy()
        self._rate_limit: dict[str, RateLimitState] = {}

    def execute(self, provider: str, req: HttpRequest) -> HttpResponse:
        provider_key = str(provider or 'unknown')
        self._validate_request(req)
        attempt = 0
        while True:
            attempt += 1
            self._wait_for_rate_limit(provider_key)
            try:
                response = self._perform(req, provider_key)
                if response.status_code in set(self._retry_policy.retryable_statuses):
                    self._update_rate_limit(provider_key, response.headers)
                    retry_after = self._read_retry_after_seconds(response.headers)
                    if self._retry_policy.should_retry(attempt=attempt, status_code=response.status_code, code='temporary_unavailable'):
                        time.sleep(self._retry_policy.sleep_seconds(attempt=attempt, retry_after_seconds=retry_after))
                        continue
                    raise HttpTransportError('temporary_unavailable', f'http status {response.status_code}', status_code=response.status_code, payload={'headers': dict(response.headers)})
                return response
            except HttpTransportError as exc:
                self._update_rate_limit(provider_key, exc.payload.get('headers') or {})
                if self._retry_policy.should_retry(attempt=attempt, status_code=exc.status_code, code=exc.code):
                    time.sleep(self._retry_policy.sleep_seconds(attempt=attempt, retry_after_seconds=self._read_retry_after_seconds(exc.payload.get('headers') or {})))
                    continue
                raise

    def _validate_request(self, req: HttpRequest) -> None:
        url = str(req.url or '').strip()
        if not url:
            raise HttpTransportError('invalid_request', 'url is required')
        parsed = parse.urlparse(url)
        if parsed.scheme not in {'http', 'https'}:
            raise HttpTransportError('invalid_request', 'only http/https urls are allowed', payload={'url': url})
        if not parsed.netloc:
            raise HttpTransportError('invalid_request', 'url host is required', payload={'url': url})

    def _wait_for_rate_limit(self, provider: str) -> None:
        state = self._rate_limit.get(provider)
        if state and state.is_blocked():
            time.sleep(max(0.0, float(state.reset_at) - time.time()))

    def _perform(self, req: HttpRequest, provider_key: str) -> HttpResponse:
        url = req.build_url()
        method = str(req.method or 'GET').upper()
        headers = {'User-Agent': 'BusinesAIOS/market-intelligence-advanced', **{str(k): str(v) for k, v in dict(req.headers or {}).items()}}
        if req.accept_json:
            headers.setdefault('Accept', 'application/json')
        data: bytes | None = None
        if req.body is not None:
            if method not in {'POST', 'PUT', 'PATCH'}:
                raise HttpTransportError('invalid_request', f'body not allowed for method {method}')
            headers.setdefault('Content-Type', 'application/json; charset=utf-8')
            data = json.dumps(dict(req.body), ensure_ascii=False).encode('utf-8')
        timeout_seconds = min(max(float(req.timeout_seconds), 1.0), 120.0)
        request_obj = request.Request(url=url, headers=headers, method=method, data=data)
        try:
            with request.urlopen(request_obj, timeout=timeout_seconds) as handle:
                payload = handle.read()
                text = payload.decode('utf-8', errors='replace')
                response_headers = {str(k): str(v) for k, v in handle.headers.items()}
                json_payload = None
                if req.accept_json:
                    try:
                        parsed_payload = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise HttpTransportError('invalid_json', 'response is not valid json', status_code=getattr(handle, 'status', None), payload={'error': str(exc), 'body_preview': text[:200]}) from exc
                    if isinstance(parsed_payload, Mapping):
                        json_payload = dict(parsed_payload)
                    elif isinstance(parsed_payload, list):
                        json_payload = tuple(dict(item) if isinstance(item, Mapping) else item for item in parsed_payload)
                    else:
                        json_payload = parsed_payload
                return HttpResponse(status_code=int(getattr(handle, 'status', 200)), headers=response_headers, text=text, json_payload=json_payload)
        except error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace') if hasattr(exc, 'read') else ''
            headers = {str(k): str(v) for k, v in getattr(exc, 'headers', {}).items()}
            self._update_rate_limit(provider_key, headers)
            raise HttpTransportError('http_error', f'http status {exc.code}', status_code=int(exc.code), payload={'headers': headers, 'body_preview': body[:200]}) from exc
        except error.URLError as exc:
            reason = getattr(exc, 'reason', exc)
            code = 'timeout' if 'timed out' in str(reason).lower() else 'transport_error'
            raise HttpTransportError(code, str(reason), payload={'reason': str(reason)}) from exc

    def _read_retry_after_seconds(self, headers: Mapping[str, Any]) -> float | None:
        value = str(dict(headers or {}).get('Retry-After') or '').strip()
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            return max(0.0, dt.timestamp() - time.time())

    def _update_rate_limit(self, provider: str, headers: Mapping[str, Any]) -> None:
        retry_after = self._read_retry_after_seconds(headers)
        if retry_after is None:
            return
        self._rate_limit[str(provider)] = RateLimitState(reset_at=time.time() + retry_after, retry_after_seconds=retry_after)


__all__ = [
    'CANON_MARKET_INTELLIGENCE_HTTP_TRANSPORT',
    'CanonicalHttpTransport',
    'HttpRequest',
    'HttpResponse',
    'HttpTransportError',
    'RateLimitState',
    'RetryPolicy',
]
