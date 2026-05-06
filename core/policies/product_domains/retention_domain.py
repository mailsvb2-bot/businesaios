from __future__ import annotations

from dataclasses import dataclass

from core.policies.telegram.helpers import ProposedAction, propose_message
from core.policies.retention.retention_keyboards import retention_main_kb


@dataclass
class RetentionDomainPolicyV1:
    def propose(self, state) -> ProposedAction:
        session = dict(getattr(state, "session", {}) or {})
        text = str(session.get("text") or "").strip()
        cb = str(session.get("callback_data") or "") if bool(session.get("is_callback")) else ""
        callback_query_id = session.get("callback_query_id")
        user_id = str(getattr(state, "user_id", "anonymous") or "anonymous")

        beh = {}
        try:
            beh = dict((getattr(state, "user", {}) or {}).get("behavioral_state") or {})
        except Exception:
            beh = {}
        engagement = float(beh.get("engagement_score") or 0.0)
        fatigue = float(beh.get("fatigue_index") or 0.0)

        if text.lower().startswith("/start"):
            return propose_message(
                user_id=user_id,
                text="Привет. Это RetentionBot. Я мягко напоминаю, когда это уместно.",
                reply_markup=retention_main_kb(),
                callback_query_id=str(callback_query_id) if callback_query_id else None,
            )

        if cb == "ret:ping":
            msg = "Я рядом. Хочешь короткую сессию или просто продолжить позже?"
            return propose_message(
                user_id=user_id,
                text=msg,
                reply_markup=retention_main_kb(),
                callback_query_id=str(callback_query_id) if callback_query_id else None,
            )

        if engagement < 0.15 and fatigue < 0.6:
            return propose_message(
                user_id=user_id,
                text="Давно не виделись. Нажми «Ping», если хочешь мягко вернуться.",
                reply_markup=retention_main_kb(),
            )
        if engagement >= 0.5:
            return propose_message(
                user_id=user_id,
                text="Ты хорошо держишь ритм. Хочешь следующий шаг? (Ping)",
                reply_markup=retention_main_kb(),
            )
        return propose_message(user_id=user_id, text="Если понадобится — просто нажми Ping.", reply_markup=retention_main_kb())
