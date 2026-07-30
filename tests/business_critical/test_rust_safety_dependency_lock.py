from __future__ import annotations

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
