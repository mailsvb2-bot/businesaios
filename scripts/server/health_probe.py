from __future__ import annotations

import json
import os

from scripts.ci.http_probe_io import fetch_text

CANON_SERVER_HEALTH_PROBE = True


def _fetch(url: str) -> tuple[int, str]:
    return fetch_text(url, method='GET', timeout=5)


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
