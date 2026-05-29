from __future__ import annotations

"""Gift links (one-time) read model.

We keep this intentionally simple and event-sourced:
- gift_token_created: {token, created_by, expires_ms}
- gift_redeemed: {token, created_by, redeemed_by}

No side-effects here. Policies may use this for validation.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class GiftTokenStatus:
    token: str
    created_by: str
    expires_ms: int
    redeemed_by: str | None = None

    @property
    def is_redeemed(self) -> bool:
        return bool(self.redeemed_by)


def get_gift_token_status(event_store: Any, *, tenant_id: str = "default", token: str) -> GiftTokenStatus | None:
    token = (token or "").strip()
    if not token:
        return None

    created_by: str | None = None
    expires_ms: int | None = None
    redeemed_by: str | None = None

    # We intentionally do a linear scan; gift events are rare.
    try:
        it = event_store.iter_events(tenant_id=str(tenant_id), start_ms=0, end_ms=None)  # type: ignore[attr-defined]
    except Exception:
        return None

    for ev in it:
        try:
            et = str(ev.get("event_type") or "")
            payload = ev.get("payload") or {}
            if et == "gift_token_created" and str(payload.get("token") or "") == token:
                created_by = str(payload.get("created_by") or "")
                try:
                    expires_ms = int(payload.get("expires_ms") or 0)
                except Exception:
                    expires_ms = 0
            if et == "gift_redeemed" and str(payload.get("token") or "") == token:
                redeemed_by = str(payload.get("redeemed_by") or "")
        except Exception:
            continue

    if not created_by:
        return None
    return GiftTokenStatus(token=token, created_by=created_by, expires_ms=int(expires_ms or 0), redeemed_by=redeemed_by)
