from __future__ import annotations

from pathlib import Path

import bootstrap.boot_phases as boot_phases
import bootstrap.world_model_forbidden_paths as scanner
from bootstrap.world_model_forbidden_paths import (
    scan_repo_for_forbidden_world_model_paths,
)
from scripts.ci.step_architecture_bypass_scan import (
    _world_model_source_guard,
)


def test_scan_repo_for_forbidden_world_model_paths(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from core.economics.ltv_world_model import WorldModel\n"
        "x = WorldModel(LTVModel())\n",
        encoding="utf-8",
    )

    findings = scan_repo_for_forbidden_world_model_paths(repo_root=tmp_path)
    assert findings
    assert any("WorldModel(LTVModel())" == f["pattern"] for f in findings)


def test_scan_prunes_generated_trees_but_keeps_canonical_test_contracts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = (
        "runtime/source.py",
        "target/debug/build/generated.py",
        "tests/test_world_model_contract_runtime.py",
        "tests/test_unrelated_runtime.py",
    )
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pass\n", encoding="utf-8")

    visited: list[str] = []

    def fake_scan_ast(_path: Path, rel: str) -> list[dict]:
        visited.append(rel)
        return []

    monkeypatch.setattr(scanner, "_scan_ast", fake_scan_ast)

    findings = scanner.scan_repo_for_forbidden_world_model_paths(
        repo_root=tmp_path
    )

    assert findings == []
    assert "runtime/source.py" in visited
    assert "tests/test_world_model_contract_runtime.py" in visited
    assert "target/debug/build/generated.py" not in visited
    assert "tests/test_unrelated_runtime.py" not in visited


def test_boot_world_model_scan_uses_the_checkout_root() -> None:
    module_path = Path(boot_phases.__file__).resolve()
    expected_root = module_path.parents[1]

    assert boot_phases._repository_root() == expected_root
    assert expected_root / "bootstrap" / "boot_phases.py" == module_path
    assert expected_root != module_path.parents[2]


def test_canonical_ci_guard_retains_fail_closed_source_enforcement(
    tmp_path: Path,
) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from core.economics.ltv_world_model import WorldModel\n"
        "x = WorldModel(LTVModel())\n",
        encoding="utf-8",
    )

    ok, message = _world_model_source_guard(tmp_path)

    assert ok is False
    assert "world model source-path scan failed" in message
    assert "WorldModel(LTVModel())" in message
