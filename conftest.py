from __future__ import annotations

import os

import pytest

# Repository test runs disable third-party plugin autoload for hermeticity.
# Load only the required async plugin in that mode. With normal autoload enabled,
# leave registration to pytest so the plugin is not registered twice.
pytest_plugins = (
    ("pytest_asyncio.plugin",)
    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"
    else ()
)


@pytest.fixture(autouse=True)
def _isolate_process_global_safety_runtime(monkeypatch):
    """Prevent one test's breaker/budget state from poisoning another test."""

    from bootstrap.safety_control_boot import build_safety_control_runtime

    monkeypatch.setenv("BUSINESAIOS_SAFETY_PERSISTENT", "0")
    build_safety_control_runtime.cache_clear()
    try:
        yield
    finally:
        build_safety_control_runtime.cache_clear()
