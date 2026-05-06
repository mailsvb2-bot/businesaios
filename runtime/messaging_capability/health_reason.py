from __future__ import annotations


def resolve_health_reason(*, ok: bool, meta: dict | None) -> str:
    if ok:
        return 'delivery_ok'
    reason = str((meta or {}).get('reason') or '')
    if reason:
        return reason
    mode = str((meta or {}).get('mode') or '')
    if mode:
        return f'failed:{mode}'
    return 'delivery_failed'
