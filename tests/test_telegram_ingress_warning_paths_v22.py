from pathlib import Path


def test_update_processor_emits_warning_not_swallow() -> None:
    txt = Path("interfaces/telegram/pipeline/update_processor.py").read_text(encoding="utf-8")
    assert "telegram_ingress_warning" in txt
    assert "swallow(__name__" not in txt
