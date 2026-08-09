from __future__ import annotations

import hashlib
from pathlib import Path


WORKFLOW = Path(".github/workflows/prune-stale-branches.yml")
AUDIT = Path(".github/branch-prune-audit.txt")
EXPECTED_WORKFLOW_SHA256 = "0fd250027f4e84826a0151e503c39d7f7975a420af20c85ad720b4ba26d5ab00"
CHECKOUT_ACTION = "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5"


def test_stale_branch_pruning_is_exactly_allowlisted() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == EXPECTED_WORKFLOW_SHA256
    assert not Path(".github/workflows/agent-branch-gc.yml").exists()
    assert not AUDIT.exists()

    # Read-only validation runner: one trusted checkout, no write token, canonical doctor.
    assert text.count(CHECKOUT_ACTION) == 1
    assert text.count("ref: ${{ github.event.pull_request.base.sha }}") == 1
    assert text.count("persist-credentials: false") == 1
    assert "github.event.pull_request.base.ref == github.event.repository.default_branch" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "startsWith(github.event.pull_request.head.ref, 'agent/')" in text
    assert text.count("python -m scripts.ci.cli --gate doctor") == 1

    validate, delete = text.split("\n  delete-merged-agent-head:\n", maxsplit=1)
    assert "contents: write" not in validate
    assert "github.token" not in validate.lower()
    assert "github['token']" not in validate.lower()
    assert 'github["token"]' not in validate.lower()
    assert "secrets." not in validate.lower()
    assert "secrets[" not in validate.lower()

    # Write runner: no checkout/repository code; one exact, revision-leased mutation script.
    assert "needs: validate-merged-agent-head" in delete
    assert "if: needs.validate-merged-agent-head.result == 'success'" in delete
    assert CHECKOUT_ACTION not in delete
    assert "uses:" not in delete
    assert delete.count("GH_TOKEN: ${{ github.token }}") == 1
    assert delete.count("git init --quiet \"$repo_dir\"") == 1
    assert delete.count("git remote add origin \"https://github.com/${GITHUB_REPOSITORY}.git\"") == 1
    assert delete.count("gh auth setup-git") == 1
    assert delete.count("git push origin") == 1
    assert delete.count('--force-with-lease="$ref:$expected_sha"') == 1
    assert delete.count('\":$ref\"; then') == 1
    assert delete.count('git ls-remote origin "$ref"') == 1
    assert "--delete" not in delete
    assert "gh api" not in delete
    assert "curl " not in delete
    assert "$GITHUB_WORKSPACE" not in delete
    assert "/git/refs/" not in delete
