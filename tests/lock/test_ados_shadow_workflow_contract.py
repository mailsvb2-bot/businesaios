from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ados-shadow.yml"


def test_ados_shadow_keeps_fork_code_off_persistent_runner() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Linux, X64, businesaios]" in text
    assert "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository" in text


def test_ados_shadow_keeps_controller_and_product_dependencies_isolated() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "$GITHUB_WORKSPACE/../.ados-runtime" in text
    assert "/project-venv" in text
    assert "/control-venv" in text
    assert "-m venv .ados-project-venv" not in text
    assert "-m venv .ados-control-venv" not in text
    assert "requirements.lock.txt" in text
    assert "cryptography==46.0.4" in text


def test_ados_command_gates_execute_project_python_outside_checkout() -> None:
    manifest = (ROOT / ".ados/commands.json").read_text(encoding="utf-8")
    assert "../.ados-runtime/project-venv/bin/python" in manifest
    assert ".ados-project-venv/bin/python" not in manifest
