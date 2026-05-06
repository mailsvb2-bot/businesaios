from __future__ import annotations

import json
import os
import urllib.request

CANON_SERVER_SMOKE_FLOW = True


def _url(path: str) -> str:
    base = os.getenv('SMOKE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    return f'{base}{path}'


def _get(path: str) -> tuple[int, dict]:
    req = urllib.request.Request(_url(path), method='GET', headers={'x-api-key': os.getenv('CONTROL_PLANE_API_KEY', 'development-control-plane-key')})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return int(getattr(resp, 'status', 0) or 0), json.loads(resp.read().decode('utf-8'))


def _post(path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        _url(path),
        data=data,
        method='POST',
        headers={
            'content-type': 'application/json',
            'x-tenant-id': os.getenv('SMOKE_TENANT_ID', 'default-business'),
            'x-idempotency-key': 'server-smoke-1',
            'x-action-id': 'server-smoke-action-1',
            'x-api-key': os.getenv('CONTROL_PLANE_API_KEY', 'development-control-plane-key'),
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return int(getattr(resp, 'status', 0) or 0), json.loads(resp.read().decode('utf-8'))


def main() -> int:
    status, health = _get('/health')
    assert status == 200 and str(health.get('status')).lower() in {'ok', 'degraded'}
    status, ready = _get('/readyz')
    assert status == 200 and str(ready.get('status')).lower() == 'ready'
    status, tenants = _get('/control-plane/admin/tenants')
    assert status == 200 and 'tenants' in tenants
    status, result = _post('/actions/execute', {'action_type': 'pricing.publish_offer', 'payload': {'offer_id': 'server-smoke-offer', 'amount': 199}})
    assert status == 200 and str(result.get('status') or '').lower() not in {'error', 'failed'}
    status, audit = _get('/control-plane/audit/actions')
    assert status == 200 and 'records' in audit
    print('SMOKE_FLOW_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
