from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("rust")
CRATE = ROOT / "businessaios_safety_core"
CARGO_TOML = CRATE / "Cargo.toml"
CARGO_LOCK = CRATE / "Cargo.lock"
TOOLCHAIN = ROOT / "rust-toolchain.toml"
POLICY = ROOT / "toolchain_policy.md"

ALLOWED_DIRECT_DEPENDENCIES = {"serde", "serde_json"}
ALLOWED_LOCK_PACKAGES = {
    "businessaios_safety_core",
    "itoa",
    "memchr",
    "proc-macro2",
    "quote",
    "serde",
    "serde_core",
    "serde_derive",
    "serde_json",
    "syn",
    "unicode-ident",
    "zmij",
}
FORBIDDEN_DEPENDENCIES = {
    "tokio",
    "reqwest",
    "hyper",
    "sqlx",
    "diesel",
    "rusqlite",
    "postgres",
    "pyo3",
    "maturin",
    "proptest",
    "rand",
    "getrandom",
}


def _section(text: str, name: str) -> str:
    marker = f"[{name}]"
    start = text.find(marker)
    if start < 0:
        return ""
    rest = text[start + len(marker):]
    next_section = rest.find("\n[")
    return rest if next_section < 0 else rest[:next_section]


def _direct_dependency_names(cargo_toml: str) -> set[str]:
    deps = set()
    for section_name in ("dependencies", "dev-dependencies", "build-dependencies"):
        section = _section(cargo_toml, section_name)
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("["):
                continue
            if "=" in stripped:
                deps.add(stripped.split("=", 1)[0].strip())
    return deps


def _lock_package_names(lock_text: str) -> set[str]:
    return set(re.findall(r'^name = "([^"]+)"$', lock_text, flags=re.MULTILINE))


def test_rust_toolchain_policy_is_explicit_and_visible() -> None:
    assert TOOLCHAIN.exists(), "rust/rust-toolchain.toml is required for MSRV determinism"
    assert POLICY.exists(), "rust/toolchain_policy.md must document safety boundaries"
    toolchain = TOOLCHAIN.read_text(encoding="utf-8")
    policy = POLICY.read_text(encoding="utf-8")

    assert 'channel = "1.75.0"' in toolchain
    assert "MSRV: Rust/Cargo `1.75.0`" in policy
    assert "DecisionCore" in policy
    assert "second policy engine" in policy
    assert "Direct FFI is not enabled" in policy


def test_rust_safety_core_uses_only_edition_2021_and_no_dev_dependencies() -> None:
    text = CARGO_TOML.read_text(encoding="utf-8")
    assert 'edition = "2021"' in text
    assert "edition = \"2024\"" not in text
    assert "[dev-dependencies]" not in text
    assert "[build-dependencies]" not in text


def test_rust_safety_core_direct_dependencies_are_allowlisted() -> None:
    text = CARGO_TOML.read_text(encoding="utf-8")
    direct = _direct_dependency_names(text)
    assert direct == ALLOWED_DIRECT_DEPENDENCIES
    assert not (direct & FORBIDDEN_DEPENDENCIES)


def test_rust_safety_core_lock_packages_are_allowlisted_and_small() -> None:
    lock_text = CARGO_LOCK.read_text(encoding="utf-8")
    packages = _lock_package_names(lock_text)
    assert packages == ALLOWED_LOCK_PACKAGES
    assert not (packages & FORBIDDEN_DEPENDENCIES)


def test_rust_safety_core_does_not_introduce_ffi_db_or_network_dependencies() -> None:
    combined = CARGO_TOML.read_text(encoding="utf-8") + "\n" + CARGO_LOCK.read_text(encoding="utf-8")
    lowered = combined.lower()
    for forbidden in FORBIDDEN_DEPENDENCIES:
        assert forbidden not in lowered, f"forbidden Rust safety dependency detected: {forbidden}"
