from __future__ import annotations

import importlib
from pathlib import Path


def test_api_handlers_are_split() -> None:
    assert Path("entrypoints/api/health_handler.py").exists()
    assert Path("entrypoints/api/execute_action_handler.py").exists()
    assert hasattr(importlib.import_module("interfaces.api.health_handler"), "HealthHandler")
    assert hasattr(importlib.import_module("interfaces.api.execute_action_handler"), "ExecuteActionHandler")
