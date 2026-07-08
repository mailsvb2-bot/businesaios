from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_legacy_canon_audit_file() -> ModuleType:
    path = Path("tools/canon_audit.py")
    spec = importlib.util.spec_from_file_location("_legacy_tools_canon_audit_py", path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_legacy_repo(root: Path) -> None:
    _write(root / "docs/SYSTEM_TZ_CANONICAL.md", "UTC canon")
    _write(
        root / "core/ai/decision_core.py",
        "class DecisionCore:\n"
        "    def decide(self):\n"
        "        return None\n",
    )
    _write(root / "core/decision_core.py", "from core.ai.decision_core import DecisionCore\n")
    _write(
        root / "runtime/executor.py",
        "class RuntimeExecutor:\n"
        "    def execute(self):\n"
        "        return execute_core_flow()\n"
        "\n"
        "def execute_core_flow():\n"
        "    return preflight_and_verify()\n"
        "\n"
        "def preflight_and_verify():\n"
        "    return True\n",
    )
    _write(
        root / "runtime/guard.py",
        "class RuntimeGuard:\n"
        "    def verify(self):\n"
        "        return True\n"
        "    def execute_once(self):\n"
        "        return True\n",
    )
    _write(root / "runtime/_internal/_effects_impl.py", "")
    _write(root / "scripts/ci/step_canon_audit.py", "")
    _write(root / "application/admin/control_plane.py", "ADMIN_SURFACE = True\n")


def test_legacy_canon_audit_file_minimal_repo_passes(tmp_path: Path) -> None:
    module = _load_legacy_canon_audit_file()
    _minimal_legacy_repo(tmp_path)

    report = module.run_operational_canon_checks(tmp_path)

    assert report.passed is True
    assert report.admission_score_100 == 100
    assert report.violation_total == 0
    assert report.warning_total == 0
    assert "passed=True" in report.format_text()


def test_legacy_canon_audit_file_detects_mandatory_and_authority_violations(tmp_path: Path) -> None:
    module = _load_legacy_canon_audit_file()

    empty_report = module.run_operational_canon_checks(tmp_path)

    assert empty_report.passed is False
    assert any(item.code == "CANON_MISSING_FILE" for item in empty_report.violations)

    _minimal_legacy_repo(tmp_path)
    _write(tmp_path / "application/rogue.py", "class DecisionEngine:\n    pass\n")

    report = module.run_operational_canon_checks(tmp_path)

    assert report.passed is False
    assert any(item.code == "CANON_SECOND_EXECUTABLE_DECISION_AUTHORITY" for item in report.violations)


def test_legacy_canon_audit_file_detects_warning_surfaces(tmp_path: Path) -> None:
    module = _load_legacy_canon_audit_file()
    _minimal_legacy_repo(tmp_path)
    _write(
        tmp_path / "application/service.py",
        "import requests\n"
        "from runtime._internal import effects\n"
        "def run():\n"
        "    return requests.get('https://example.test')\n",
    )

    report = module.run_operational_canon_checks(tmp_path)

    assert report.passed is True
    codes = {item.code for item in report.warnings}
    assert "CANON_PRIVATE_EFFECTS_IMPORT" in codes
    assert "CANON_RAW_SIDE_EFFECT_IMPORT" in codes


def test_legacy_canon_audit_file_helpers_cover_import_and_format_paths(tmp_path: Path) -> None:
    module = _load_legacy_canon_audit_file()

    _write(tmp_path / "application/live.py", "import os\nfrom pathlib import Path\n")
    _write(tmp_path / "reports/generated.py", "")
    _write(tmp_path / ".venv/ignored.py", "")

    files = sorted(path.relative_to(tmp_path).as_posix() for path in module._iter_py_files(tmp_path))
    assert files == ["application/live.py"]

    tree = ast.parse("import os\nfrom pathlib import Path\n")
    roots = []
    modules = []
    for node in ast.walk(tree):
        roots.extend(module._import_roots(node))
        modules.extend(module._import_modules(node))

    assert "os" in roots
    assert "pathlib" in roots
    assert "os" in modules
    assert "pathlib" in modules

    items = tuple(
        module.CanonViolation("X", f"path_{index}.py", "message")
        for index in range(module.MAX_REPORTED_ITEMS + 2)
    )
    report = module.CanonAuditReport(
        passed=False,
        admission_score_100=0,
        violations=items[: module.MAX_REPORTED_ITEMS],
        warnings=items[: module.MAX_REPORTED_ITEMS],
        checked_files=1,
        violation_total=len(items),
        warning_total=len(items),
    )

    text = report.format_text()
    assert "VIOLATION output truncated: 2 more" in text
    assert "WARNING output truncated: 2 more" in text
