from __future__ import annotations

from pathlib import Path

from scripts.ci.config import project_shape_config

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deep-release-validation.yml"


def test_deep_release_workflow_is_part_of_the_canonical_project_shape() -> None:
    config = project_shape_config(ROOT)

    assert WORKFLOW.relative_to(ROOT).as_posix() in config.allowed_workflows


def test_deep_release_workflow_is_exact_head_read_only_and_same_repo_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "contents: read" in text
    assert "persist-credentials: false" in text
    assert "Verify exact checkout" in text
    assert "git rev-parse HEAD" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text


def test_deep_release_workflow_uses_canonical_gates_and_real_probes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "--gate postgres-migrations" in text
    assert "pg_dump" in text
    assert "run_staging_runtime_proof.sh" in text
    assert "--gate staging-runtime" in text
    assert "--gate release" in text
    assert "docker pull python:3.12-slim" in text
    assert "POSTGRES_BACKUP_EVIDENCE_OK=1" not in text
