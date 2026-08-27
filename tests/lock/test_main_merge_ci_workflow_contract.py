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
MERGED_TARGET_GUARD = "github.event_name != 'pull_request_target' || github.event.pull_request.merged == true"
UNMERGED_TARGET_GROUP = "format('pr-{0}-closed-unmerged', github.event.pull_request.number)"
TARGET_SCOPED_CONCURRENCY = "group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.event_name == 'push' && github.sha || github.event_name == 'pull_request_target' && github.event.pull_request.merged == true && github.event.pull_request.merge_commit_sha || github.event_name == 'pull_request_target' && format('pr-{0}-closed-unmerged', github.event.pull_request.number) || github.ref }}"
ORDINARY_PR_TYPES = "  pull_request:\n    types:\n      - opened\n      - synchronize\n      - reopened\n  pull_request_target:\n    types:\n      - closed"


def test_mandatory_ci_uses_reliable_merged_pr_event_and_exact_main_commit() -> None:
    for relative in MANDATORY:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert ORDINARY_PR_TYPES in text
        assert MERGE_SHA in text
        assert TARGET_ENV in text
        assert MERGED_TARGET_GUARD in text
        assert "ref: ${{ env.BAIOS_CI_TARGET_SHA }}" in text
        assert "EXPECTED_SHA: ${{ env.BAIOS_CI_TARGET_SHA }}" in text
        assert "github.event_name == 'pull_request_target'" in text


def test_mandatory_ci_concurrency_is_scoped_to_target_identity() -> None:
    for relative in MANDATORY:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert TARGET_SCOPED_CONCURRENCY in text
        assert UNMERGED_TARGET_GROUP in text
        assert "group: ${{ github.workflow }}-${{ github.ref }}" not in text


def test_targeted_ci_uses_pre_change_base_for_push_and_merged_events() -> None:
    text = (ROOT / ".github/workflows/targeted-domain-ci.yml").read_text(encoding="utf-8")
    assert "BAIOS_TARGETED_BASE_SHA:" in text
    assert "github.event_name == 'push' && github.event.before" in text
    assert "github.event_name == 'pull_request_target'" in text
    assert "github.event.pull_request.base.sha" in text
    assert 'if [ -n "$BAIOS_TARGETED_BASE_SHA" ]; then' in text
    assert 'TARGETED_CI_BASE=$BAIOS_TARGETED_BASE_SHA' in text
    assert 'TARGETED_CI_BASE=origin/main' in text
    assert "TARGETED_CI_BASE: origin/main" not in text


def test_deep_release_keeps_untrusted_pr_head_blocked_but_allows_merged_commit() -> None:
    text = (ROOT / ".github/workflows/deep-release-validation.yml").read_text(encoding="utf-8")
    assert "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository" in text
    assert MERGED_TARGET_GUARD in text
    assert "GIT_COMMIT_SHA: ${{ env.BAIOS_CI_TARGET_SHA }}" in text
    assert "deep-release-${{ env.BAIOS_CI_TARGET_SHA }}" in text
