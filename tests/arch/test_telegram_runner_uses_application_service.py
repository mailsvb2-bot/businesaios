from pathlib import Path


def test_telegram_runner_uses_application_service() -> None:
    text = Path("interfaces/telegram/telegram_runner_integration.py").read_text(
        encoding="utf-8"
    )

    assert "application_service" in text
    assert "build_runtime(" not in text
    assert "registry.get(" not in text
