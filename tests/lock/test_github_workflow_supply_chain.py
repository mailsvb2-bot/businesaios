from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
ACTION_SHA = re.compile(r"^[0-9a-f]{40}$")
IMAGE_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _workflow_files() -> tuple[Path, ...]:
    return tuple(sorted(WORKFLOW_DIR.glob("*.yml")))


def _yaml_value(line: str, key: str) -> str | None:
    stripped = line.strip()
    prefix = f"{key}:"
    if stripped.startswith("- "):
        stripped = stripped[2:].lstrip()
    if not stripped.startswith(prefix):
        return None
    value = stripped[len(prefix):].split(" #", 1)[0].strip()
    return value.strip("'\"")


def test_external_actions_are_pinned_to_immutable_commit_shas() -> None:
    violations: list[str] = []
    for workflow in _workflow_files():
        for line_number, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            value = _yaml_value(line, "uses")
            if value is None or value.startswith("./"):
                continue
            _, separator, ref = value.rpartition("@")
            if not separator or ACTION_SHA.fullmatch(ref) is None:
                violations.append(f"{workflow.name}:{line_number}:{value}")

    assert not violations, "floating GitHub Actions references: " + ", ".join(violations)


def test_workflow_service_images_are_digest_pinned() -> None:
    violations: list[str] = []
    for workflow in _workflow_files():
        for line_number, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            value = _yaml_value(line, "image")
            if value is not None and IMAGE_DIGEST.search(value) is None:
                violations.append(f"{workflow.name}:{line_number}:{value}")

    assert not violations, "floating workflow service images: " + ", ".join(violations)


def test_pull_request_workflows_verify_exact_head_without_credentials() -> None:
    violations: list[str] = []
    for workflow in _workflow_files():
        text = workflow.read_text(encoding="utf-8")
        if "pull_request:" not in text:
            continue
        required = (
            "persist-credentials: false",
            "Verify exact checkout",
            "git rev-parse HEAD",
        )
        missing = [item for item in required if item not in text]
        if missing:
            violations.append(f"{workflow.name}:{','.join(missing)}")

    assert not violations, "non-exact PR workflows: " + ", ".join(violations)
