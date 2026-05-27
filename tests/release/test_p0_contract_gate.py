from __future__ import annotations

import shutil
from pathlib import Path

from scripts.ci.p0_contract_gate import run_p0_contract_gate


def _ignore_release_runtime_artifacts(dirpath: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}:
            ignored.add(name)
        if name.endswith((".pyc", ".pyo")):
            ignored.add(name)
    return ignored


def test_p0_contract_gate_passes_for_release_projection(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    projected = tmp_path / "repo"
    shutil.copytree(root, projected, ignore=_ignore_release_runtime_artifacts)
    result = run_p0_contract_gate(projected)
    assert result.ok, "\n".join(result.failures)
