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
TARGET_ENV = "BAIOS_CI_TARGET_SHA"
SAME_REPO_PR_GUARD = "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository"
SELF_HOSTED_RUNNER = "runs-on: [self-hosted, Linux, X64, businesaios]"
SELF_HOSTED_MANDATORY = tuple(path for path in MANDATORY if path != ".github/workflows/deep-release-validation.yml")
TARGET_SCOPED_CONCURRENCY = "group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.event_name == 'push' && github.sha || github.ref }}"
ORDINARY_PR_TYPES = "  pull_request:\n    types:\n      - opened\n      - synchronize\n      - reopened"
EXACT_TARGET = "${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}"


def test_mandatory_ci_checks_pr_and_exact_main_commit_without_privileged_target_event() -> None:
    for relative in MANDATORY:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "  push:\n    branches:\n      - main" in text
        assert ORDINARY_PR_TYPES in text
        assert "pull_request_target" not in text
        assert TARGET_ENV in text
        assert f"{TARGET_ENV}: {EXACT_TARGET}" in text
        assert "ref: ${{ env.BAIOS_CI_TARGET_SHA }}" in text
        assert "EXPECTED_SHA: ${{ env.BAIOS_CI_TARGET_SHA }}" in text


def test_self_hosted_mandatory_ci_rejects_fork_pr_heads() -> None:
    for relative in SELF_HOSTED_MANDATORY:
        text = (ROOT / relative).read_text(encoding="utf-8")
        runner_count = text.count(SELF_HOSTED_RUNNER)
        assert runner_count >= 1
        assert text.count(SAME_REPO_PR_GUARD) == runner_count


def test_mandatory_ci_concurrency_is_scoped_to_push_sha_or_pr_ref() -> None:
    for relative in MANDATORY:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert TARGET_SCOPED_CONCURRENCY in text
        assert "cancel-in-progress: true" in text
        assert "group: ${{ github.workflow }}-${{ github.ref }}" not in text


def test_targeted_ci_uses_pre_change_base_without_network_fetch() -> None:
    text = (ROOT / ".github/workflows/targeted-domain-ci.yml").read_text(encoding="utf-8")
    assert "BAIOS_TARGETED_BASE_SHA:" in text
    assert "github.event_name == 'push' && github.event.before" in text
    assert "github.event_name == 'pull_request' && github.event.pull_request.base.sha" in text
    assert "pull_request_target" not in text
    assert 'if [ -n "$BAIOS_TARGETED_BASE_SHA" ]; then' in text
    assert "TARGETED_CI_BASE=$BAIOS_TARGETED_BASE_SHA" in text
    assert "TARGETED_CI_BASE=origin/main" in text
    assert "TARGETED_CI_BASE: origin/main" not in text


def test_deep_release_blocks_untrusted_pr_and_keeps_exact_commit_evidence() -> None:
    text = (ROOT / ".github/workflows/deep-release-validation.yml").read_text(encoding="utf-8")
    assert SAME_REPO_PR_GUARD in text
    assert "pull_request_target" not in text
    assert "GIT_COMMIT_SHA: ${{ env.BAIOS_CI_TARGET_SHA }}" in text
    assert "deep-release-${{ env.BAIOS_CI_TARGET_SHA }}" in text
