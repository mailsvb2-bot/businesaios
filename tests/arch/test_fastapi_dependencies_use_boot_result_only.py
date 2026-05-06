from __future__ import annotations

import importlib
from pathlib import Path


def test_fastapi_dependencies_use_boot_result_only() -> None:
    text = Path("adapters/api/fastapi/dependencies.py").read_text(encoding="utf-8")

    assert "AppBootResult" in text
    assert "RuntimeRegistry" not in text
    assert "ReadOnlyRuntimeRegistry" not in text
    assert "build_runtime(" not in text
    assert hasattr(importlib.import_module("interfaces.api.fastapi_dependencies"), "FastAPIDependencyContainer")
