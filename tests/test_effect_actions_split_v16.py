from pathlib import Path


def test_telegram_effects_use_helper_modules() -> None:
    path = Path(__file__).resolve().parents[1] / "runtime" / "_internal" / "effects_actions" / "telegram_actions.py"
    src = path.read_text(encoding="utf-8")
    assert "telegram_self_check_effect" in src
    assert "send_message_effect" in src


def test_payments_effects_use_yookassa_helper_module() -> None:
    path = Path(__file__).resolve().parents[1] / "runtime" / "_internal" / "effects_actions" / "payments_actions.py"
    src = path.read_text(encoding="utf-8")
    assert "yookassa_create_payment" in src
    assert "start_webhook_server" in src
