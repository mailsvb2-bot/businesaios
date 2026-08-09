from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/prune-stale-branches.yml")
AUDIT = Path(".github/branch-prune-audit.txt")


def test_stale_branch_pruning_keeps_only_revision_atomic_merged_pr_cleanup() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert not Path(".github/workflows/agent-branch-gc.yml").exists()
    assert not AUDIT.exists()
    assert "pull_request_target" not in text
    assert "concurrency:" not in text
    assert "\n  push:\n" not in text
    assert "prune-audited-stale-branches" not in text
    assert "branch-prune-audit.txt" not in text
    assert "github.event.pull_request.merged == true" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "startsWith(github.event.pull_request.head.ref, 'agent/')" in text
    assert "EXPECTED_SHA: ${{ github.event.pull_request.head.sha }}" in text
    assert text.count("contents: write") == 1
    assert text.count("persist-credentials: false") == 1
    assert text.count("gh auth setup-git") == 1
    assert text.count('--force-with-lease="$ref:$expected_sha"') == 1
    assert text.count('git ls-remote origin "$ref"') == 1
    assert "/git/refs/" not in text
    assert "Delete every non-default branch" not in text
