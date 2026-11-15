from __future__ import annotations

import re
from pathlib import Path

from tests._infra.tracked_files import DELIVERY_SCAN_EXCLUDED_DIRS, tracked_files

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATE_DIR = REPO_ROOT / "rust/businessaios_safety_core"


def test_rust_safety_core_has_reproducible_dependency_lock() -> None:
    cargo_toml = CRATE_DIR / "Cargo.toml"
    cargo_lock = CRATE_DIR / "Cargo.lock"

    assert cargo_toml.exists(), "Rust safety core Cargo.toml is required"
    assert cargo_lock.exists(), (
        "Rust safety core Cargo.lock must be committed for reproducible release gates"
    )

    lock_text = cargo_lock.read_text(encoding="utf-8")
    assert "name = \"businessaios_safety_core\"" in lock_text
    assert "name = \"serde\"" in lock_text
    assert "name = \"serde_json\"" in lock_text
    assert "name = \"proptest\"" not in lock_text


def test_rust_safety_core_target_directory_is_not_tracked() -> None:
    fallback_excluded_dirs = DELIVERY_SCAN_EXCLUDED_DIRS - {"target"}
    offenders = tuple(
        path.relative_to(REPO_ROOT).as_posix()
        for path in tracked_files(
            REPO_ROOT,
            "rust/businessaios_safety_core/target",
            fallback_excluded_dirs=fallback_excluded_dirs,
        )
    )
    assert offenders == (), "Rust target/ must stay local and must not be committed"


WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


def test_release_python_lock_is_transitive_exact_and_hash_pinned() -> None:
    lock = (REPO_ROOT / "requirements.release.lock.txt").read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^(?=[A-Za-z0-9_.-]+(?:\[[^\]]+\])?==)", lock)[1:]
    blocks = [block for block in blocks if block.strip()]
    assert len(blocks) >= 30
    assert all("--hash=sha256:" in block for block in blocks)
    assert not re.search(r"(git\+|https?://|file:|@ )", re.sub(r"(?m)^\s*#.*$", "", lock))


def test_direct_python_requirements_are_exactly_pinned() -> None:
    for name in ("requirements.txt", "requirements.lock.txt"):
        lines = [
            line.strip()
            for line in (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "-"))
        ]
        assert lines and all("==" in line for line in lines), name


def test_docker_and_deep_release_install_only_the_hashed_release_lock() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "pip install --require-hashes -r requirements.release.lock.txt" in dockerfile
    deep_release = (REPO_ROOT / ".github/workflows/deep-release-validation.yml").read_text(encoding="utf-8")
    assert "pip install --require-hashes -r requirements.release.lock.txt" in deep_release


def test_workflow_dependency_installs_use_the_hashed_transitive_lock() -> None:
    assert len(WORKFLOWS) >= 5
    for workflow in WORKFLOWS:
        for line in workflow.read_text(encoding="utf-8").splitlines():
            if "pip install" in line and ("requirements.lock.txt" in line or "requirements.release.lock.txt" in line):
                assert "--require-hashes" in line and "requirements.release.lock.txt" in line, (
                    f"{workflow.name}: Python workflow install must use the hashed transitive lock: {line.strip()}"
                )


def test_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8")
        matches = list(re.finditer(r"(?m)^[ \t]*(?:-[ \t]+)?uses:[ \t]+(\S+)", text))
        assert "uses:" not in text or matches, f"{workflow.name}: action matcher must inspect YAML uses steps"
        for match in matches:
            ref = match.group(1)
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            action, _, version = ref.partition("@")
            assert action and _SHA40.fullmatch(version), (
                f"{workflow.name}: action must be pinned to a full commit SHA: {ref}"
            )


def test_pull_request_dependency_review_is_strict_and_sha_pinned() -> None:
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294" in workflow
    assert "fail-on-severity: low" in workflow
    assert "fail-on-scopes: runtime, development, unknown" in workflow
    assert "warn-only: true" not in workflow

def test_release_lock_has_platform_specific_windows_dependencies() -> None:
    lock = (REPO_ROOT / "requirements.release.lock.txt").read_text(encoding="utf-8")
    lines = lock.splitlines()
    uvloop_lines = [line for line in lines if line.startswith("uvloop==")]
    tzdata_lines = [line for line in lines if line.startswith("tzdata==")]
    assert len(uvloop_lines) == 1
    assert 'sys_platform != "win32"' in uvloop_lines[0]
    assert len(tzdata_lines) == 1
    assert 'sys_platform == "win32"' in tzdata_lines[0]
    tzdata_index = lines.index(tzdata_lines[0])
    tzdata_block = "\n".join(lines[tzdata_index:tzdata_index + 4])
    assert "--hash=sha256:0a10eec6e13ef16b627fabed9a5f2ba61a62b1c67f327305f4e7e412a70b4aec" in tzdata_block
    assert "--hash=sha256:85d2cd9c09f81f0bb29db27759fc83af4f1e620efb814f8c5bf8b4cc4feece6d" in tzdata_block

