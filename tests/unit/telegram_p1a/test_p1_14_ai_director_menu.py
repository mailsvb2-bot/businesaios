"""P1-14: «ИИ-директор» is reachable from the AI section and leads to ceo:plan / ceo:run."""

from __future__ import annotations

from core.policies.telegram.router import handle
from core.ux.unified_messenger_menu import menu_items, plain_channel_menu
from tests.unit.telegram_p1a._support import decide, make_ctx


def _callbacks(markup):
    return [b.get("callback_data") for row in markup["inline_keyboard"] for b in row]


def test_main_menu_ai_section_is_the_ai_director_entry():
    item = next(i for i in menu_items(role="owner") if i.key == "ai")
    assert "ИИ-директор" in item.label and item.callback == "autopilot:menu"
    assert any(a["key"] == "ai" for a in plain_channel_menu(channel="vk", role="owner")["actions"])


def test_ai_section_shows_ai_director_for_owner_and_marketer_only():
    for role, visible in (("owner", True), ("marketer", True), ("operator", False)):
        ctx = make_ctx(user_id="1001", callback_data="autopilot:menu", roles=[role])
        out = handle(ctx, default_price_rub=990)
        cbs = _callbacks(out.payload["reply_markup"])
        assert ("ceo:menu" in cbs) is visible, role
        assert cbs[-1] == "menu:main"


def test_ai_director_screen_runs_only_for_owner():
    owner = make_ctx(user_id="1001", callback_data="ceo:menu", roles=["owner"])
    action, payload = decide(handle(owner, default_price_rub=990), owner)
    assert action == "ai_ceo_plan@v1"
    assert {"ceo:plan", "ceo:run", "autopilot:menu"} <= set(_callbacks(payload["reply_markup"]))
    marketer = make_ctx(user_id="2002", callback_data="ceo:menu", roles=["marketer"])
    _, payload = decide(handle(marketer, default_price_rub=990), marketer)
    assert "ceo:run" not in _callbacks(payload["reply_markup"])
