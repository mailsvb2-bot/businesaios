from __future__ import annotations

from types import SimpleNamespace

from runtime.admin_state_support import perform_admin_toggle
from runtime.guard import RuntimeGuard


class _Verifier:
    def verify(self, envelope):
        return True


class _Survival:
    def evaluate(self, envelope):
        return object()


class _Ledger:
    pass


class _EventLog:
    def __init__(self):
        self.rows = []

    def emit(self, **kwargs):
        self.rows.append(kwargs)


class _Owner:
    def __init__(self):
        self.answered = []
        self.sent = []

    def _telegram_answer_callback(self, callback_query_id: str):
        self.answered.append(callback_query_id)

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return {"ok": True, "message_id": 1}


def test_runtime_guard_reference_mode_keeps_production_methods_blocked_after_split():
    guard = RuntimeGuard(_Survival(), _Ledger(), _Verifier())
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d1"))

    for method_name in ("verify", "execute_once", "verify_recovery"):
        method = getattr(guard, method_name)
        try:
            method(env)
        except RuntimeError as exc:
            assert "only available in production mode" in str(exc)
        else:
            raise AssertionError(f"{method_name} unexpectedly allowed in reference mode")


def test_perform_admin_toggle_preserves_event_and_notification_contract():
    owner = _Owner()
    log = _EventLog()

    result = perform_admin_toggle(
        owner,
        decision_id="d-1",
        correlation_id="c-1",
        admin_id="admin-7",
        target_user_id="user-9",
        field_name="role",
        field_value="ops",
        enabled=True,
        notify_text="done",
        notify_reply_markup={"inline_keyboard": []},
        callback_query_id="cb-1",
        channel="telegram",
        event_log=log,
    )

    assert result["ok"] is True
    assert owner.answered == ["cb-1"]
    assert owner.sent and owner.sent[0]["user_id"] == "admin-7"
    assert log.rows[0]["event_type"] == "admin_role_set"
    assert log.rows[0]["payload"]["target_user_id"] == "user-9"
    assert log.rows[1]["event_type"] == "admin_notification_sent"
