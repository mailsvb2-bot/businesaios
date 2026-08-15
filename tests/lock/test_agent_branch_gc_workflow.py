from __future__ import annotations

import hashlib
import re
from pathlib import Path


WORKFLOW = Path(".github/workflows/prune-stale-branches.yml")
AUDIT = Path(".github/branch-prune-audit.txt")
REQUEST = Path(".github/branch-prune-request.tsv")
EXPECTED_WORKFLOW_SHA256 = "4eb09122af7442837b37adac2e15ed58d1816d14865f3049388bd8b2477482cd"
CHECKOUT_ACTION = "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _workflow_sections(text: str) -> tuple[str, str, str, str]:
    validate_merged, tail = text.split("\n  delete-merged-agent-head:\n", maxsplit=1)
    delete_merged, tail = tail.split("\n  validate-snapshot-prune:\n", maxsplit=1)
    validate_snapshot, delete_snapshot = tail.split("\n  delete-snapshot-branches:\n", maxsplit=1)
    return validate_merged, delete_merged, validate_snapshot, delete_snapshot


def test_stale_branch_pruning_is_exactly_allowlisted() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == EXPECTED_WORKFLOW_SHA256
    assert not Path(".github/workflows/agent-branch-gc.yml").exists()
    assert not AUDIT.exists()
    assert REQUEST.exists()

    validate_merged, delete_merged, validate_snapshot, delete_snapshot = _workflow_sections(text)

    # Merged-PR validation runner: trusted base checkout, no write token, canonical doctor.
    assert validate_merged.count(CHECKOUT_ACTION) == 1
    assert validate_merged.count("ref: ${{ github.event.pull_request.base.sha }}") == 1
    assert validate_merged.count("persist-credentials: false") == 1
    assert validate_merged.count("Verify exact checkout") == 1
    assert "github.event.pull_request.base.ref == github.event.repository.default_branch" in validate_merged
    assert "github.event.pull_request.head.repo.full_name == github.repository" in validate_merged
    assert "startsWith(github.event.pull_request.head.ref, 'agent/')" in validate_merged
    assert validate_merged.count("python -m scripts.ci.cli --gate doctor") == 1
    assert "contents: write" not in validate_merged
    assert "github.token" not in validate_merged.lower()
    assert "github['token']" not in validate_merged.lower()
    assert 'github["token"]' not in validate_merged.lower()
    assert "secrets." not in validate_merged.lower()
    assert "secrets[" not in validate_merged.lower()

    # Merged-PR write runner: no repository checkout; exact revision-leased deletion only.
    assert "needs: validate-merged-agent-head" in delete_merged
    assert "if: needs.validate-merged-agent-head.result == 'success'" in delete_merged
    assert CHECKOUT_ACTION not in delete_merged
    assert "uses:" not in delete_merged
    assert delete_merged.count("GH_TOKEN: ${{ github.token }}") == 1
    assert delete_merged.count("git init --quiet \"$repo_dir\"") == 1
    assert delete_merged.count("git remote add origin \"https://github.com/${GITHUB_REPOSITORY}.git\"") == 1
    assert delete_merged.count("gh auth setup-git") == 1
    assert delete_merged.count("git push origin") == 1
    assert delete_merged.count('--force-with-lease="$ref:$expected_sha"') == 1
    assert delete_merged.count('\":$ref\"; then') == 1
    assert delete_merged.count('git ls-remote origin "$ref"') == 1
    assert "preserved_changed_ref=" in delete_merged
    assert "--delete" not in delete_merged
    assert "gh api" not in delete_merged
    assert "curl " not in delete_merged
    assert "$GITHUB_WORKSPACE" not in delete_merged
    assert "/git/refs/" not in delete_merged

    # Snapshot validation runner: only exact main revision can authorize the bounded request.
    assert "if: github.event_name == 'push'" in validate_snapshot
    assert validate_snapshot.count(CHECKOUT_ACTION) == 1
    assert validate_snapshot.count("ref: ${{ github.sha }}") == 1
    assert validate_snapshot.count("persist-credentials: false") == 1
    assert 'test "$(git rev-parse HEAD)" = "$TRUSTED_HEAD_SHA"' in validate_snapshot
    assert "test -s .github/branch-prune-request.tsv" in validate_snapshot
    assert '"$branch" != "main"' in validate_snapshot
    assert validate_snapshot.count("python -m scripts.ci.cli --gate doctor") == 1
    assert "contents: write" not in validate_snapshot
    assert "github.token" not in validate_snapshot.lower()
    assert "secrets." not in validate_snapshot.lower()
    assert "secrets[" not in validate_snapshot.lower()

    # Snapshot write runner may inspect open PRs, but still deletes only an unchanged leased ref.
    assert "needs: validate-snapshot-prune" in delete_snapshot
    assert "if: needs.validate-snapshot-prune.result == 'success'" in delete_snapshot
    assert "contents: write" in delete_snapshot
    assert "pull-requests: read" in delete_snapshot
    assert delete_snapshot.count(CHECKOUT_ACTION) == 1
    assert delete_snapshot.count("ref: ${{ github.sha }}") == 1
    assert delete_snapshot.count("persist-credentials: false") == 1
    assert delete_snapshot.count("GH_TOKEN: ${{ github.token }}") == 1
    assert delete_snapshot.count("git init --quiet \"$repo_dir\"") == 1
    assert delete_snapshot.count("git remote add origin \"https://github.com/${GITHUB_REPOSITORY}.git\"") == 1
    assert delete_snapshot.count("gh auth setup-git") == 1
    assert 'default_branch="${{ github.event.repository.default_branch }}"' in delete_snapshot
    assert '"$branch" != "$default_branch"' in delete_snapshot
    assert delete_snapshot.count('git ls-remote origin "$ref"') == 1
    assert "preserved_changed_ref=" in delete_snapshot
    assert delete_snapshot.count("gh api --paginate") == 1
    assert "pulls?state=open&head=${owner}:${branch}&per_page=100" in delete_snapshot
    assert "preserved_open_pr_head=" in delete_snapshot
    assert delete_snapshot.count('--force-with-lease="$ref:$expected_sha"') == 1
    assert delete_snapshot.count('git push origin --force-with-lease="$ref:$expected_sha" ":$ref"') == 1
    assert '$GITHUB_WORKSPACE/.github/branch-prune-request.tsv' in delete_snapshot
    assert '"$preserved" -eq 0' in delete_snapshot
    assert "--delete" not in delete_snapshot
    assert "curl " not in delete_snapshot
    assert "/git/refs/" not in delete_snapshot


def test_snapshot_prune_request_is_bounded_and_never_targets_main() -> None:
    rows: list[tuple[str, str]] = []
    for raw_line in REQUEST.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = raw_line.split("\t")
        assert len(parts) == 2
        branch, expected_sha = parts
        assert branch and branch != "main"
        assert not branch.startswith("refs/")
        assert SHA40.fullmatch(expected_sha)
        rows.append((branch, expected_sha))

    assert rows
    assert len(rows) == len({branch for branch, _ in rows})
