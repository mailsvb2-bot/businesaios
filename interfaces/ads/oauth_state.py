from __future__ import annotations

"""Canonical OAuth state helpers for Ads connectors.

We keep this small and stable:
  - state = "{tenant_id}:{unix_ts}"

Validation is done in the web layer (where you have session/cookie context).
Here we only provide a consistent generator/parser to avoid "second lines"
and copy/paste drift across connectors.
"""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class OAuthState:
    tenant_id: str
    issued_at_ts: int


def build_state(*, tenant_id: str) -> str:
    ts = int(datetime.now(UTC).timestamp())
    return f"{tenant_id}:{ts}"


def parse_state(state: str) -> OAuthState | None:
    try:
        tenant, ts_s = state.split(":", 1)
        return OAuthState(tenant_id=tenant, issued_at_ts=int(ts_s))
    except Exception:
        return None
