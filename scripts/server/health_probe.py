from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

CANON_SERVER_HEALTH_PROBE = True


def _fetch(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return int(getattr(resp, 'status', 0) or 0), resp.read().decode('utf-8', errors='replace')


def main() -> int:
    url = os.getenv('HEALTH_URL', 'http://127.0.0.1:8000/readyz').strip() or 'http://127.0.0.1:8000/readyz'
    try:
        status, body = _fetch(url)
    except urllib.error.URLError as exc:  # pragma: no cover
        raise SystemExit(f'HEALTH_PROBE_FAILED:{exc.reason}') from exc
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
