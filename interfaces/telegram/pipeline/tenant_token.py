from __future__ import annotations

"""Tenant token parsing for Telegram deep links.

Supported formats:
  /start tenant:<TENANT_ID>
  /start t_<TENANT_ID>
  /tenant <TENANT_ID>

We intentionally keep parsing dumb and explicit.
"""

from typing import Optional


def parse_tenant_token(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None

    # /start <arg>
    if t.lower().startswith("/start"):
        parts = t.split(maxsplit=1)
        if len(parts) == 2:
            return _parse_arg(parts[1])

    # /tenant <tenant_id>
    if t.lower().startswith("/tenant"):
        parts = t.split(maxsplit=1)
        if len(parts) == 2:
            return parts[1].strip() or None

    return None


def _parse_arg(arg: str) -> str | None:
    a = (arg or "").strip()
    if not a:
        return None
    if a.lower().startswith("tenant:"):
        return a.split(":", 1)[1].strip() or None
    if a.lower().startswith("t_"):
        return a[2:].strip() or None
    return None
