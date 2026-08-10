from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANDATORY = (
    ".github/workflows/ci-doctor.yml",
    ".github/workflows/ci-fast.yml",
    ".github/workflows/ci-full.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/deep-release-validation.yml",
    ".github/workflows/full-ci.yml",
    ".github/workflows/targeted-domain-ci.yml",
)
MERGE_SHA = "github.event.pull_request.merge_commit_sha"
TARGET_ENV = "BAIOS_CI_TARGET_SHA"
CLOSED_GUARD = "github.event.action != 'closed' || github.event.pull_request.merged == true"


def test_mandatory_ci_runs_on_merged_pr_and_targets_exact_main_commit() -> None:
    for relative in MANDATORY:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "- opened" in text
        assert "- synchronize" in text
        assert "- reopened" in text
        assert "- closed" in text
        assert MERGE_SHA in text
        assert TARGET_ENV in text
        assert CLOSED_GUARD in text
        assert "ref: ${{ env.BAIOS_CI_TARGET_SHA }}" in text
        assert "EXPECTED_SHA: ${{ env.BAIOS_CI_TARGET_SHA }}" in text


def test_deep_release_keeps_untrusted_pr_head_blocked_but_allows_merged_commit() -> None:
    text = (ROOT / ".github/workflows/deep-release-validation.yml").read_text(encoding="utf-8")
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "github.event.action == 'closed'" in text
    assert "GIT_COMMIT_SHA: ${{ env.BAIOS_CI_TARGET_SHA }}" in text
    assert "deep-release-${{ env.BAIOS_CI_TARGET_SHA }}" in text
