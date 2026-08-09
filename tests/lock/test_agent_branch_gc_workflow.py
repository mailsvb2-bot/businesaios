from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/prune-stale-branches.yml")
AUDIT = Path(".github/branch-prune-audit.txt")


def test_stale_branch_pruning_keeps_only_revision_atomic_merged_pr_cleanup() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert not Path(".github/workflows/agent-branch-gc.yml").exists()
    assert not AUDIT.exists()
    assert "pull_request_target" not in text
    assert "concurrency:" not in text
    assert "\n  push:\n" not in text
    assert "prune-audited-stale-branches" not in text
    assert "branch-prune-audit.txt" not in text
    assert "github.event.pull_request.merged == true" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "github.event.pull_request.base.ref == github.event.repository.default_branch" in text
    assert "startsWith(github.event.pull_request.head.ref, 'agent/')" in text
    assert "EXPECTED_SHA: ${{ github.event.pull_request.head.sha }}" in text
    assert "TRUSTED_BASE_SHA: ${{ github.event.pull_request.base.sha }}" in text
    assert text.count("ref: ${{ github.event.pull_request.base.sha }}") == 1
    assert "ref: ${{ github.event.pull_request.head.sha }}" not in text
    assert text.count("contents: write") == 1
    assert text.count("persist-credentials: false") == 1

    doctor = "python -m scripts.ci.cli --gate doctor"
    assert text.count(doctor) == 1
    assert text.count("GH_TOKEN: ${{ github.token }}") == 2
    assert "GH_TOKEN:" not in text[: text.index(doctor)]
    assert text.index(doctor) < text.index("GH_TOKEN:") < text.index("gh auth setup-git")

    assert text.count("gh auth setup-git") == 1
    assert text.count("git push") == 1
    assert text.count("git push origin") == 1
    assert "--delete" not in text
    assert "gh api" not in text
    assert "curl " not in text
    assert "/git/refs/" not in text

    push_index = next(index for index, line in enumerate(lines) if "git push origin" in line)
    assert lines[push_index].strip() == "if git push origin \\" 
    assert lines[push_index + 1].strip() == '--force-with-lease="$ref:$expected_sha" \\'
    assert lines[push_index + 2].strip() == '":$ref"; then'
    assert text.count('git ls-remote origin "$ref"') == 1
    assert "Delete every non-default branch" not in text
