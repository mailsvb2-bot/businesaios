from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Mapping

CANON_CI_HTTP_PROBE_IO = True


def fetch_text(url: str, *, method: str = 'GET', headers: Mapping[str, str] | None = None, body: bytes | None = None, timeout: float = 10.0) -> tuple[int, str]:
    req = urllib.request.Request(str(url), data=body, method=str(method or 'GET').upper(), headers={str(k): str(v) for k, v in dict(headers or {}).items()})
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            return int(getattr(resp, 'status', 0) or 0), resp.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        return int(getattr(exc, 'code', 0) or 0), exc.read().decode('utf-8')


def fetch_json(url: str, *, method: str = 'GET', headers: Mapping[str, str] | None = None, payload: Mapping[str, object] | None = None, timeout: float = 10.0) -> tuple[int, dict]:
    body = None
    final_headers = {str(k): str(v) for k, v in dict(headers or {}).items()}
    if payload is not None:
        body = json.dumps(dict(payload), sort_keys=True).encode('utf-8')
        final_headers.setdefault('content-type', 'application/json')
    status, text = fetch_text(url, method=method, headers=final_headers, body=body, timeout=timeout)
    return status, json.loads(text or '{}')


__all__ = ['CANON_CI_HTTP_PROBE_IO', 'fetch_json', 'fetch_text']
