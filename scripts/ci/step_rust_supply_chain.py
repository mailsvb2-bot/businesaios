from __future__ import annotations

import json
import shutil
import subprocess

from scripts.ci.paths import repo_root


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
FORBIDDEN_MARKERS = {
    "pyo3",
    "maturin",
    "tokio",
    "reqwest",
    "hyper",
    "sqlx",
    "diesel",
    "rusqlite",
    "postgres",
    "rand",
    "getrandom",
    "proptest",
}


def _package_names(lock_text: str) -> set[str]:
    names: set[str] = set()
    for line in lock_text.splitlines():
        stripped = line.strip()
        if stripped.startswith('name = "') and stripped.endswith('"'):
            names.add(stripped.split('"', 2)[1])
    return names


def _direct_deps(cargo_toml: str) -> set[str]:
    in_dependencies = False
    names: set[str] = set()
    for line in cargo_toml.splitlines():
        stripped = line.strip()
        if stripped == "[dependencies]":
            in_dependencies = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_dependencies = False
        if in_dependencies and stripped and not stripped.startswith("#") and "=" in stripped:
            names.add(stripped.split("=", 1)[0].strip())
    return names


def _write_report(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "rust_supply_chain.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run() -> tuple[bool, str]:
    root = repo_root()
    crate = root / "rust" / "businessaios_safety_core"
    cargo_toml_path = crate / "Cargo.toml"
    cargo_lock_path = crate / "Cargo.lock"
    toolchain_path = root / "rust" / "rust-toolchain.toml"
    if not cargo_toml_path.exists() or not cargo_lock_path.exists() or not toolchain_path.exists():
        return False, "rust safety supply chain policy files missing"
    cargo_toml = cargo_toml_path.read_text(encoding="utf-8")
    cargo_lock = cargo_lock_path.read_text(encoding="utf-8")
    toolchain = toolchain_path.read_text(encoding="utf-8")
    direct_deps = _direct_deps(cargo_toml)
    lock_packages = _package_names(cargo_lock)
    violations: list[str] = []
    if 'channel = "1.75.0"' not in toolchain:
        violations.append("msrv_not_pinned_to_1_75_0")
    if 'edition = "2021"' not in cargo_toml or 'edition = "2024"' in cargo_toml:
        violations.append("rust_edition_policy_violation")
    if "[dev-dependencies]" in cargo_toml or "[build-dependencies]" in cargo_toml:
        violations.append("dev_or_build_dependencies_forbidden")
    if direct_deps != ALLOWED_DIRECT_DEPENDENCIES:
        violations.append("direct_dependency_allowlist_violation")
    if lock_packages != ALLOWED_LOCK_PACKAGES:
        violations.append("lock_package_allowlist_violation")
    lowered = (cargo_toml + "\n" + cargo_lock).lower()
    for marker in sorted(FORBIDDEN_MARKERS):
        if marker in lowered:
            violations.append(f"forbidden_dependency_marker:{marker}")
    cargo_audit = shutil.which("cargo-audit") or shutil.which("cargo-audit.exe")
    audit_available = cargo_audit is not None
    audit_status = "unavailable"
    if cargo_audit is not None:
        completed = subprocess.run([cargo_audit, "audit"], cwd=crate, capture_output=True, text=True, timeout=180)
        audit_status = "passed" if completed.returncode == 0 else "failed"
        if completed.returncode != 0:
            violations.append("cargo_audit_failed")
    report = {
        "artifact": "rust_supply_chain",
        "passed": not violations,
        "msrv": "1.75.0",
        "edition": "2021",
        "direct_dependencies": sorted(direct_deps),
        "lock_packages": sorted(lock_packages),
        "cargo_audit_available": audit_available,
        "cargo_audit_status": audit_status,
        "violations": violations,
    }
    _write_report(report)
    if violations:
        return False, "rust safety supply chain violations: " + ", ".join(violations[:5])
    suffix = "cargo-audit unavailable; allowlist policy passed" if not audit_available else "cargo-audit passed; allowlist policy passed"
    return True, f"rust safety supply chain diagnostic passed ({suffix})"


__all__ = ["run"]
