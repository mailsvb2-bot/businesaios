from __future__ import annotations

import subprocess
from pathlib import Path

CRATE_DIR = Path("rust/businessaios_safety_core")


def test_rust_safety_core_has_reproducible_dependency_lock() -> None:
    cargo_toml = CRATE_DIR / "Cargo.toml"
    cargo_lock = CRATE_DIR / "Cargo.lock"

    assert cargo_toml.exists(), "Rust safety core Cargo.toml is required"
    assert cargo_lock.exists(), "Rust safety core Cargo.lock must be committed for reproducible release gates"

    lock_text = cargo_lock.read_text(encoding="utf-8")
    assert "name = \"businessaios_safety_core\"" in lock_text
    assert "name = \"serde\"" in lock_text
    assert "name = \"serde_json\"" in lock_text
    assert "name = \"proptest\"" not in lock_text


def test_rust_safety_core_target_directory_is_not_tracked() -> None:
    completed = subprocess.run(
        ["git", "ls-files", "rust/businessaios_safety_core/target"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "", "Rust target/ must stay local and must not be committed"
