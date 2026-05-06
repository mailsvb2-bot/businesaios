from __future__ import annotations

import importlib
from pathlib import Path


def test_handlers_wiring_is_not_god_module_anymore():
    text = Path("bootstrap/handlers_wiring.py").read_text(encoding="utf-8")
    assert "register_messaging_handlers" in text
    assert "register_growth_handlers" in text
    assert "register_ops_handlers" in text
    assert "register_ads_handlers" in text
    assert len(text.splitlines()) < 120
    assert importlib.import_module('runtime.boot.handlers_wiring') is not None
