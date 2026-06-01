from core.users.roles import UserRoleInfo
from core.ux.telegram_keyboards import kb_ads_apply_pending, kb_growth_menu, kb_main


def test_ads_apply_pending_respects_can_apply_flag():
    kb = kb_ads_apply_pending(can_apply=False)
    flat = [b["text"] for row in kb["inline_keyboard"] for b in row]
    assert "🛑 Применение выключено" in flat
    assert "✅ Применить (подтвердить)" not in flat


def test_main_keyboard_keeps_ads_apply_for_marketer():
    kb = kb_main(role=UserRoleInfo("marketer"))
    flat = [b["text"] for row in kb["inline_keyboard"] for b in row]
    assert "🧩 Ads Apply (prod)" in flat


def test_growth_menu_facade_still_available():
    kb = kb_growth_menu()
    assert kb["inline_keyboard"][0][0]["callback_data"] == "growth:generate"
