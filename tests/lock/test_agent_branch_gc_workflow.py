from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/prune-stale-branches.yml")


def _bootstrap_branches(text: str) -> list[str]:
    marker = "      BOOTSTRAP_BRANCHES: |\n"
    start = text.index(marker) + len(marker)
    end = text.index("    steps:\n", start)
    return [line.strip() for line in text[start:end].splitlines() if line.strip()]


def test_stale_branch_pruning_uses_one_fail_closed_owner() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert not Path(".github/workflows/agent-branch-gc.yml").exists()
    assert "pull_request_target" not in text
    assert "github.event.pull_request.merged == true" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "startsWith(github.event.pull_request.head.ref, 'agent/')" in text
    assert "cancel-in-progress: false" in text
    assert text.count("contents: write") == 2
    assert 'request("GET", f"{api_root}/git/ref/{encoded_ref}")' in text
    assert 'request("DELETE", f"{api_root}/git/refs/{encoded_ref}")' in text
    assert "Delete every non-default branch" not in text


def test_stale_branch_bootstrap_is_exact_audited_allowlist() -> None:
    branches = _bootstrap_branches(WORKFLOW.read_text(encoding="utf-8"))

    assert len(branches) == 50
    assert len(branches) == len(set(branches))
    assert all(branch.startswith("agent/") for branch in branches)
    assert "main" not in branches
    assert "agent/branch-gc-bootstrap" in branches
