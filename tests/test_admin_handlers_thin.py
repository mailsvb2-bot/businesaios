from __future__ import annotations

from types import SimpleNamespace

from core.policies.telegram.handlers.admin.analytics import handle_analytics
from core.policies.telegram.handlers.admin_handlers import handle_admin


class _Ctx(SimpleNamespace):
    is_admin = True
    is_superadmin = False
    perms = []
    roles = ["admin"]
    cmd = ""
    args = ""
    callback_query_id = "cq1"
    state = SimpleNamespace(user_id="42", tenant_id="t1")
    admin_metrics = {
        "funnel": {
            "tariffs_viewed": 10,
            "tariff_selected": 5,
            "payment_created": 3,
            "payment_succeeded": 2,
            "access_granted": 2,
            "audio_sent": 1,
        }
    }
    moods = []
    event_store = None
    chat_id = "100"


def _pm(**kwargs):
    return kwargs


def test_admin_funnel_callback_works_after_split() -> None:
    ctx = _Ctx(callback_data="admin:funnel")
    out = handle_analytics(ctx, user_id="42", pm=_pm)
    assert out is not None
    assert "Воронка" in out["text"]
    assert "tariffs" not in out["text"].lower()  # localized user text, not debug garbage


def test_admin_handlers_file_stays_thin() -> None:
    import pathlib

    text = pathlib.Path("core/policies/telegram/handlers/admin_handlers.py").read_text(encoding="utf-8")
    assert len(text.splitlines()) < 60


def test_admin_orchestrator_delegates() -> None:
    ctx = _Ctx(callback_data="admin:funnel")
    out = handle_admin(ctx, user_id="42", pm=_pm)
    assert out is not None
    assert "Воронка" in out["text"]
