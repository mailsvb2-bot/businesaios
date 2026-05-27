from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_execution_package_root_installs_public_api_alias_directly() -> None:
    text = (ROOT / "execution" / "__init__.py").read_text(encoding="utf-8")
    assert 'importlib.import_module("execution.public_api")' not in text
    assert "compat_api = import_module('execution.public_api')" not in text
    assert 'CANON_EXECUTION_ROOT_DIRECT_OWNER_EXPORTS = True' in text
    assert 'install_public_api_alias(__name__)' in text


def test_execution_package_root_uses_direct_owner_modules_for_high_value_exports() -> None:
    text = (ROOT / "execution" / "__init__.py").read_text(encoding="utf-8")
    for expected in [
        "('execution.headless_contract', 'GoalExecutionRequest')",
        "('execution.headless_boot', 'HeadlessRuntime')",
        "('execution.business_operating_memory', 'BusinessOperatingMemory')",
        "('execution.governance_service', 'GovernanceService')",
        "('execution.business_memory_matcher', 'BusinessMemoryMatcher')",
    ]:
        assert expected in text
