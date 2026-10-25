"""Prove that critical security regressions fail when controls are deliberately broken.

Mutations run in isolated child Python processes; production code is never
modified and the parent pytest process cannot retain an injected defect.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# The injected faults must be caught by the unchanged project tests.
MUTATIONS = (
    (
        "tenant_required_fail_open",
        "contracts.tenant_identity",
        "require_tenant_id",
        "def broken(value):\n    return str(value or '').strip()\n",
        "tests/business_critical/test_tenant_negative_contracts.py::test_strict_tenant_id_refuses_missing_and_placeholder_values",
    ),
    (
        "ledger_execute_twice",
        "runtime.inmemory_ledger",
        "InMemoryLedger.try_mark_executed",
        "def broken(self, envelope):\n    return True\n",
        "tests/business_critical/test_execute_once_ledger_contract.py::test_second_claim_of_same_decision_id_is_refused",
    ),
)


@pytest.mark.parametrize(("mutation", "module", "symbol", "fault", "test_target"), MUTATIONS)
def test_security_suite_kills_injected_control_failure(
    tmp_path: Path, mutation: str, module: str, symbol: str, fault: str, test_target: str,
) -> None:
    plugin = tmp_path / "security_fault_plugin.py"
    plugin.write_text(
        "import importlib\n"
        "def pytest_configure(config):\n"
        f"    mod = importlib.import_module({module!r})\n"
        + "".join("    " + line + "\n" for line in fault.rstrip().splitlines())
        + ("    owner, attr = " + repr(symbol.split(".", 1)) + "\n"
           "    setattr(getattr(mod, owner), attr, broken)\n"
           if "." in symbol else f"    setattr(mod, {symbol!r}, broken)\n"),
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(tmp_path), str(ROOT), env.get("PYTHONPATH", "")))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "security_fault_plugin", test_target],
        cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=90, check=False,
    )
    assert result.returncode == 1, (
        f"SECURITY_MUTATION_SURVIVED: {mutation}; "
        f"pytest exit={result.returncode}; output={result.stdout[-3000:]}"
    )
    assert "failed" in result.stdout.lower(), (
        f"SECURITY_MUTATION_NOT_OBSERVED: {mutation}; output={result.stdout[-3000:]}"
    )
