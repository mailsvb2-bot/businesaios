from __future__ import annotations

import os
from pathlib import Path

import pytest

# Repository test runs disable third-party plugin autoload for hermeticity.
# Load only the required async plugin in that mode. With normal autoload enabled,
# leave registration to pytest so the plugin is not registered twice.
pytest_plugins = (
    ("pytest_asyncio.plugin",)
    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"
    else ()
)

_ROOT = Path(__file__).resolve().parent
_KNOWN_FULL_SUITE_DEBT = _ROOT / "tests" / "known_full_suite_debt.txt"


def _load_known_full_suite_debt() -> frozenset[str]:
    if not _KNOWN_FULL_SUITE_DEBT.exists():
        return frozenset()
    return frozenset(
        line.strip()
        for line in _KNOWN_FULL_SUITE_DEBT.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _is_complete_tree_request(config: pytest.Config) -> bool:
    if os.environ.get("BUSINESAIOS_RUN_KNOWN_FULL_SUITE_DEBT", "").strip() == "1":
        return False
    args = [str(arg).replace("\\", "/").rstrip("/") for arg in config.args]
    if not args:
        return True
    return len(args) == 1 and (args[0] == "tests" or args[0].endswith("/tests"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Quarantine only exact, recorded historical contracts in a full-tree run.

    Targeted and canonical CI shards still execute every requested test. A developer
    can also force the debt set to run with BUSINESAIOS_RUN_KNOWN_FULL_SUITE_DEBT=1.
    """

    if not _is_complete_tree_request(config):
        return
    known_debt = _load_known_full_suite_debt()
    if not known_debt:
        return
    marker = pytest.mark.skip(
        reason=(
            "known full-suite contract debt; canonical gates remain mandatory; "
            "set BUSINESAIOS_RUN_KNOWN_FULL_SUITE_DEBT=1 to execute"
        )
    )
    quarantined = 0
    for item in items:
        if item.nodeid in known_debt:
            item.add_marker(marker)
            quarantined += 1
    setattr(config, "_businesaios_quarantined_contracts", quarantined)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    del exitstatus
    quarantined = int(getattr(config, "_businesaios_quarantined_contracts", 0))
    if quarantined:
        terminalreporter.write_sep(
            "-",
            f"known full-suite contract debt quarantined: {quarantined}",
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
