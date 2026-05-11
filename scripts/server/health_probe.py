from __future__ import annotations

import json
import os

from runtime._internal.http_transport import sync_request

CANON_SERVER_HEALTH_PROBE = True


def _fetch(url: str) -> tuple[int, str]:
    result = sync_request(method='GET', url=url, timeout_s=5)
    if result.error_kind:
        raise RuntimeError(result.error_message or result.error_kind)
    return int(result.status or 0), str(result.text or '')


def main() -> int:
    url = os.getenv('HEALTH_URL', 'http://127.0.0.1:8000/readyz').strip() or 'http://127.0.0.1:8000/readyz'
    try:
        status, body = _fetch(url)
    except RuntimeError as exc:  # pragma: no cover
        raise SystemExit(f'HEALTH_PROBE_FAILED:{exc}') from exc
    if status != 200:
        raise SystemExit(f'HEALTH_PROBE_FAILED:{status}')
    payload = json.loads(body)
    state = str(payload.get('status') or '').lower()
    if state not in {'ok', 'ready'}:
        raise SystemExit(f'HEALTH_PROBE_FAILED:status={state}')
    print('HEALTH_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
