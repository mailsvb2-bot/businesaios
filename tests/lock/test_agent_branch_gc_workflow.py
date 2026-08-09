from __future__ import annotations

import re
from pathlib import Path


WORKFLOW = Path(".github/workflows/prune-stale-branches.yml")
AUDIT = Path(".github/branch-prune-audit.txt")


def _job_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    jobs_index = lines.index("jobs:")
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines[jobs_index + 1 :], start=jobs_index + 1):
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            starts.append((index, line.strip()[:-1]))

    blocks: dict[str, str] = {}
    for offset, (start, name) in enumerate(starts):
        end = starts[offset + 1][0] if offset + 1 < len(starts) else len(lines)
        blocks[name] = "\n".join(lines[start:end])
    return blocks


def _step_blocks(job_block: str) -> list[str]:
    lines = job_block.splitlines()
    steps_index = next(index for index, line in enumerate(lines) if line == "    steps:")
    starts = [
        index
        for index, line in enumerate(lines[steps_index + 1 :], start=steps_index + 1)
        if line.startswith("      - ")
    ]
    return [
        "\n".join(lines[start : starts[offset + 1] if offset + 1 < len(starts) else len(lines)])
        for offset, start in enumerate(starts)
    ]


def test_stale_branch_pruning_keeps_only_revision_atomic_merged_pr_cleanup() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    jobs = _job_blocks(text)

    assert not Path(".github/workflows/agent-branch-gc.yml").exists()
    assert not AUDIT.exists()
    assert set(jobs) == {"validate-merged-agent-head", "delete-merged-agent-head"}
    assert "pull_request_target" not in text
    assert "concurrency:" not in text
    assert "\n  push:\n" not in text
    assert "prune-audited-stale-branches" not in text
    assert "branch-prune-audit.txt" not in text

    validate = jobs["validate-merged-agent-head"]
    delete = jobs["delete-merged-agent-head"]
    validate_steps = _step_blocks(validate)
    delete_steps = _step_blocks(delete)

    assert "github.event.pull_request.merged == true" in validate
    assert "github.event.pull_request.head.repo.full_name == github.repository" in validate
    assert "github.event.pull_request.base.ref == github.event.repository.default_branch" in validate
    assert "startsWith(github.event.pull_request.head.ref, 'agent/')" in validate
    assert "contents: read" in validate
    assert "contents: write" not in validate
    assert "write-all" not in validate

    checkout_steps = [step for step in validate_steps + delete_steps if "uses: actions/checkout@" in step]
    assert len(checkout_steps) == 1
    checkout = checkout_steps[0]
    assert checkout in validate_steps
    assert "ref: ${{ github.event.pull_request.base.sha }}" in checkout
    assert "persist-credentials: false" in checkout
    assert "github.event.pull_request.head.sha" not in checkout
    assert all("uses: actions/checkout@" not in step for step in delete_steps)

    doctor = "python -m scripts.ci.cli --gate doctor"
    doctor_steps = [step for step in validate_steps if doctor in step]
    assert len(doctor_steps) == 1
    assert not re.search(r"\$\{\{[^}]*\bsecrets\b", validate, flags=re.IGNORECASE)
    assert not re.search(r"\bgithub\.token\b", validate, flags=re.IGNORECASE)
    assert not re.search(r"^\s*[A-Za-z0-9_-]*token\s*:", validate, flags=re.IGNORECASE | re.MULTILINE)

    assert "needs: validate-merged-agent-head" in delete
    assert "if: needs.validate-merged-agent-head.result == 'success'" in delete
    assert "contents: write" in delete
    assert len(delete_steps) == 1
    mutation = delete_steps[0]
    assert "uses:" not in mutation
    assert mutation.count("GH_TOKEN: ${{ github.token }}") == 1
    assert "secrets." not in mutation
    assert "gh auth setup-git" in mutation
    assert "git init --quiet \"$repo_dir\"" in mutation
    assert "git remote add origin \"https://github.com/${GITHUB_REPOSITORY}.git\"" in mutation
    assert "$GITHUB_WORKSPACE" not in mutation
    assert "--delete" not in mutation
    assert "gh api" not in mutation
    assert "curl " not in mutation
    assert "/git/refs/" not in mutation
    assert mutation.count("git push") == 1
    assert mutation.count("git push origin") == 1

    lines = mutation.splitlines()
    push_index = next(index for index, line in enumerate(lines) if "git push origin" in line)
    assert lines[push_index].strip() == "if git push origin \\"
    assert lines[push_index + 1].strip() == '--force-with-lease="$ref:$expected_sha" \\'
    assert lines[push_index + 2].strip() == '":$ref"; then'
    assert mutation.count('git ls-remote origin "$ref"') == 1
    assert "Delete every non-default branch" not in text
