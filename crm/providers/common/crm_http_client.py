from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from runtime.effects import encode_form_body, url_with_params
from runtime.firewall.import_guard import ALLOW_INTERNAL_IMPORT

from crm.providers.common.crm_http_errors import (
    CrmAuthenticationError,
    CrmHttpErrorContext,
    CrmRateLimitError,
    CrmResponseError,
    CrmTimeoutError,
    CrmTransportError,
)
from crm.providers.common.crm_rate_limit_policy import CrmRateLimitPolicy
from crm.providers.common.crm_retry_policy import CrmRetryPolicy


def _load_internal_attr(module_name: str, attr_name: str) -> Any:
    token = ALLOW_INTERNAL_IMPORT.set(True)
    try:
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)
    finally:
        ALLOW_INTERNAL_IMPORT.reset(token)


def _sync_request(*args: Any, **kwargs: Any) -> Any:
    return _load_internal_attr('runtime._internal.http_transport', 'sync_request')(*args, **kwargs)


@dataclass(frozen=True)
class CrmHttpRequest:
    method: str
    path: str
    headers: Mapping[str, str] = field(default_factory=dict)
    query_params: Mapping[str, object] = field(default_factory=dict)
    json_body: Mapping[str, object] | None = None
    form_body: Mapping[str, object] | None = None
    raw_body: bytes | None = None
    timeout_seconds: float = 15.0


@dataclass(frozen=True)
class CrmHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    json_body: object | None
    text: str


class CrmHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        default_headers: Mapping[str, str] | None = None,
        retry_policy: CrmRetryPolicy | None = None,
        rate_limit_policy: CrmRateLimitPolicy | None = None,
        opener: Callable[..., object] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._default_headers = dict(default_headers or {})
        self._retry_policy = retry_policy or CrmRetryPolicy()
        self._rate_limit_policy = rate_limit_policy or CrmRateLimitPolicy()
        self._opener = opener

    def send(self, request_spec: CrmHttpRequest) -> CrmHttpResponse:
        attempt = 1
        while True:
            try:
                return self._send_once(request_spec, attempt=attempt)
            except (CrmTimeoutError, CrmTransportError, CrmRateLimitError, CrmResponseError, CrmAuthenticationError) as exc:
                decision = self._retry_policy.evaluate(exc)
                if not decision.should_retry:
                    raise
                time.sleep(max(decision.delay_seconds, 0.0))
                attempt += 1

    def _send_once(self, request_spec: CrmHttpRequest, *, attempt: int) -> CrmHttpResponse:
        url = self._build_url(request_spec.path, request_spec.query_params)
        headers = dict(self._default_headers)
        headers.update(request_spec.headers)
        data = self._build_body(request_spec, headers)
        result = _sync_request(
            method=request_spec.method.upper(),
            url=url,
            headers=headers,
            body=data,
            timeout_s=request_spec.timeout_seconds,
            opener=self._opener,
        )
        if result.error_kind == 'timeout':
            context = CrmHttpErrorContext(method=request_spec.method.upper(), url=url, attempt=attempt)
            raise CrmTimeoutError('CRM request timed out', context=context)
        if result.error_kind == 'transport_error':
            context = CrmHttpErrorContext(method=request_spec.method.upper(), url=url, attempt=attempt)
            detail = result.error_message or 'transport failure'
            raise CrmTransportError(f'CRM transport error: {detail}', context=context)
        if result.error_kind == 'http_error':
            status_code = int(result.status or 500)
            context = CrmHttpErrorContext(
                method=request_spec.method.upper(),
                url=url,
                status_code=status_code,
                response_headers=dict(result.headers),
                response_text=result.text,
                attempt=attempt,
            )
            if status_code in {401, 403}:
                raise CrmAuthenticationError(f'CRM authentication failed: {status_code}', context=context)
            if status_code == 429:
                raise CrmRateLimitError('CRM rate limit reached', context=context)
            raise CrmResponseError(f'CRM response error: {status_code}', context=context)
        status_code = int(result.status or 200)
        self._rate_limit_policy.validate(requests_per_minute=0)
        return CrmHttpResponse(
            status_code=status_code,
            headers=dict(result.headers),
            json_body=result.json if result.json is not None else self._try_json(result.text),
            text=result.text,
        )

    def _build_body(self, request_spec: CrmHttpRequest, headers: dict[str, str]) -> bytes | None:
        populated = sum(x is not None for x in (request_spec.json_body, request_spec.form_body, request_spec.raw_body))
        if populated > 1:
            raise ValueError('Only one of json_body, form_body, or raw_body may be supplied')
        if request_spec.raw_body is not None:
            return request_spec.raw_body
        if request_spec.form_body is not None:
            headers.setdefault('Content-Type', 'application/x-www-form-urlencoded')
            pairs: dict[str, object] = {}
            for key, value in request_spec.form_body.items():
                if value is None:
                    continue
                pairs[str(key)] = value
            return encode_form_body(pairs)
        if request_spec.json_body is not None:
            headers.setdefault('Content-Type', 'application/json')
            return json.dumps(request_spec.json_body).encode('utf-8')
        return None

    def _build_url(self, path: str, params: Mapping[str, object]) -> str:
        clean_path = '' if not path else (path if path.startswith('/') else f'/{path}')
        url = f'{self._base_url}{clean_path}'
        if not params:
            return url
        return url_with_params(url=url, params=dict(params))

    @staticmethod
    def _try_json(text: str) -> object | None:
        if not text.strip():
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
