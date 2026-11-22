"""Security regression: analytics callbacks deny non-admins before reading the store."""

from __future__ import annotations

import pytest

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.handlers.admin.analytics import handle_analytics
from core.policies.telegram.helpers import ProposedAction

CALLBACKS = (
    "admin:demo:brief",
    "admin:demo:full",
    "admin:users:today",
    "admin:segments",
    "admin:ab",
    "admin:giftshare",
    "admin:funnel2",
    "admin:funnel",
    "admin:latency",
    "admin:retention",
    "admin:user:card",
    "admin:state:last",
)
DENIED = "Доступ запрещён."


class _Store:
    def __init__(self) -> None:
        self.touched: list[str] = []

    def __getattr__(self, name: str):
        self.touched.append(name)
        raise AttributeError(name)


class _State:
    user_id = "u1"
    tenant_id = "t1"
    product: dict = {}
    economy: dict = {}


class _Ctx:
    def __init__(self, callback: str, *, is_admin: bool, store: _Store) -> None:
        self._ctx = TelegramCtx(
            state=_State(),
            text="",
            cmd="",
            args="",
            callback_data=callback,
            callback_query_id=None,
            settings={},
            city="",
            moods=[],
            admin_metrics={},
            is_admin=is_admin,
            roles=[],
            perms=[],
            is_superadmin=False,
            realtime_state={},
            pricing_suggestions={},
            full_access=False,
            pay_status="none",
            selected_tariff={},
            marketing_variants={},
            marketing_seed="1",
            marketing_bandit={},
        )
        self.event_store = store

    def __getattr__(self, name: str):
        return getattr(self._ctx, name)


def _pm(**kwargs):
    return kwargs


@pytest.mark.parametrize("callback", CALLBACKS)
def test_non_admin_is_denied_before_event_store_access(callback: str) -> None:
    store = _Store()
    out = handle_analytics(_Ctx(callback, is_admin=False, store=store), user_id="u1", pm=_pm)
    assert out is not None and out["text"] == DENIED
    assert store.touched == []


def test_admin_is_not_unconditionally_denied_for_the_same_callbacks() -> None:
    denied: list[str] = []
    for callback in CALLBACKS:
        try:
            out = handle_analytics(_Ctx(callback, is_admin=True, store=_Store()), user_id="u1", pm=_pm)
        except (AttributeError, KeyError, TypeError, ValueError):
            # The recording store intentionally has no data; a non-denial is enough
            # to prove the handler did not apply the non-admin branch unconditionally.
            continue
        if isinstance(out, ProposedAction):
            message = out.payload.get("text")
        elif isinstance(out, dict):
            message = out.get("text")
        else:
            message = None
        if message == DENIED:
            denied.append(callback)
    assert denied == []
