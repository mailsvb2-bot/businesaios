from __future__ import annotations

import importlib
from pathlib import Path


def test_error_presenters_do_not_access_runtime() -> None:
    text = Path("entrypoints/api/error_presenter.py").read_text(encoding="utf-8")
    assert "registry" not in text
    assert "RuntimeRegistry" not in text
    text = Path("interfaces/telegram/telegram_error_presenter.py").read_text(encoding="utf-8")
    assert "registry" not in text
    assert "RuntimeRegistry" not in text
    assert hasattr(importlib.import_module("interfaces.api.error_presenter"), "present_api_error")
