from pathlib import Path


def test_admin_read_model_is_facade_only():
    root = Path(__file__).resolve().parents[1]
    text = (root / "core" / "admin" / "read_model.py").read_text(encoding="utf-8")
    assert "from core.admin.read_models import" in text
    assert "def users_today" not in text
    assert len(text.splitlines()) < 80
