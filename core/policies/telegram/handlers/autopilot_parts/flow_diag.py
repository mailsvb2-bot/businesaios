from __future__ import annotations

from core.policies.telegram.handlers.autopilot_parts.flow_catalog import resolve_offer_choices
from core.policies.telegram.handlers.autopilot_parts.shared import kb_pick_offer, set_session
from core.ux.telegram_keyboards import kb_back_main


def _parse_int(text: str) -> int:
    try:
        return int("".join(ch for ch in text if ch.isdigit()) or "0")
    except Exception:
        return 0


def handle_diag_text(ctx, *, user_id: str, default_price_rub: int, sess: dict):
    diag = dict(sess.get("diag") or {}) if isinstance(sess.get("diag"), dict) else {}
    text = ctx.text.strip()
    stage = str(sess.get("stage") or "")
    if stage == "diag:what":
        diag["what"] = text[:200]
        sess["stage"] = "diag:avg_check"
        sess["diag"] = diag
        return set_session(user_id=user_id, sess=sess, notify_text="2) Средний чек (в ₽, число)?", reply_markup=kb_back_main(), callback_query_id=None)
    if stage == "diag:avg_check":
        diag["avg_check_rub"] = _parse_int(text)
        sess["stage"] = "diag:margin"
        sess["diag"] = diag
        return set_session(user_id=user_id, sess=sess, notify_text="3) Маржа (%) примерно?", reply_markup=kb_back_main(), callback_query_id=None)
    if stage == "diag:margin":
        diag["margin_pct"] = _parse_int(text)
        sess["stage"] = "diag:leads"
        sess["diag"] = diag
        return set_session(user_id=user_id, sess=sess, notify_text="4) Сколько лидов в день сейчас? (число)", reply_markup=kb_back_main(), callback_query_id=None)
    if stage != "diag:leads":
        return None

    diag["leads_per_day"] = _parse_int(text)
    sess["stage"] = "pick:offer"
    sess["diag"] = diag
    offers = resolve_offer_choices(ctx, default_price_rub=default_price_rub)
    return set_session(user_id=user_id, sess=sess, notify_text="Шаг 1/4 — Выбери оффер (из каталога):", reply_markup=kb_pick_offer(offers), callback_query_id=None)
