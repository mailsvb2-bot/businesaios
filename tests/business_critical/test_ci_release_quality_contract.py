from __future__ import annotations

import os
from pathlib import Path

from scripts.ci.config import project_shape_config
from scripts.ci.execution import _step_environment
from scripts.ci.step_project_shape import run as run_project_shape
from scripts.ci.step_quality import _quality_tools_required


def test_project_shape_enforces_actual_workflow_allowlist() -> None:
    root = Path.cwd()
    cfg = project_shape_config(root)
    actual = tuple(sorted(path.relative_to(root).as_posix() for path in (root / ".github" / "workflows").glob("*.yml")))

    assert actual == tuple(sorted(cfg.allowed_workflows))
    ok, message = run_project_shape()
    assert ok is True, message


def test_pyproject_is_required_and_contains_canonical_surface() -> None:
    cfg = project_shape_config(Path.cwd())
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "pyproject.toml" in cfg.required_paths
    assert "canonical_ci_cli" in text
    assert "DecisionCore" in text
    assert "alpha-staging-read-only-advisory" in text


def test_release_quality_gate_requires_quality_tools_only_for_release_steps(monkeypatch) -> None:
    monkeypatch.delenv("BAIOS_REQUIRE_QUALITY_TOOLS", raising=False)
    assert _quality_tools_required() is False

    with _step_environment(gate="release", step_name="quality-check"):
        assert os.environ["BAIOS_REQUIRE_QUALITY_TOOLS"] == "release"
        assert _quality_tools_required() is True

    assert "BAIOS_REQUIRE_QUALITY_TOOLS" not in os.environ


def test_full_quality_gate_does_not_force_release_tooling(monkeypatch) -> None:
    monkeypatch.delenv("BAIOS_REQUIRE_QUALITY_TOOLS", raising=False)

    with _step_environment(gate="full", step_name="quality-check"):
        assert _quality_tools_required() is False
