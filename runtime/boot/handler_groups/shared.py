from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


def get_ctx_value(ctx, key: str):
    try:
        return ctx.get_value(key)
    except Exception:
        return None
