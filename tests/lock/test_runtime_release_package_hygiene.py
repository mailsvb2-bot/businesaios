from __future__ import annotations

from pathlib import Path

from core.security.release_runtime_surface import (
    iter_runtime_release_files,
    runtime_release_member_violations,
)

ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, rel: str, value: str = "x") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_runtime_release_excludes_build_state_logs_and_internal_reports(
    tmp_path: Path,
) -> None:
    allowed = (
        "Dockerfile",
        "VERSION",
        "main.py",
        "requirements.release.lock.txt",
        "runtime/service.py",
        "rust/businessaios_safety_core/Cargo.lock",
        "rust/businessaios_safety_core/src/lib.rs",
    )
    excluded = (
        "runtime/data/demo/security/process_owner_security_audit.jsonl",
        "runtime/data/business_autonomy/action_ledger.jsonl",
        "reports/integrity/integrity.json",
        "rust/businessaios_safety_core/target/debug/libcore.rlib",
        "rust/businessaios_safety_core/target/.rustc_info.json",
        "CANON_MERGE_REPORT_2026-05-06.md",
        "COMPILE_TRIAGE_REPORT_round20.txt",
        "RELEASE_CLEANING_REPORT.md",
        "desktop.ini",
        "state.db-journal",
    )
    for rel in (*allowed, *excluded):
        _write(tmp_path, rel)

    members = {
        path.relative_to(tmp_path).as_posix()
        for path in iter_runtime_release_files(tmp_path)
    }

    assert set(allowed) <= members
    assert not (set(excluded) & members)
    assert runtime_release_member_violations(sorted(members)) == ()


def test_release_member_contract_rejects_traversal_duplicates_and_junk() -> None:
    clean = {
        "Dockerfile",
        "VERSION",
        "main.py",
        "requirements.release.lock.txt",
        "rust/businessaios_safety_core/Cargo.lock",
    }
    members = [
        *sorted(clean),
        "runtime/data/demo/state.jsonl",
        "rust/businessaios_safety_core/target/debug/lib.rlib",
        "../escape.txt",
        "main.py",
    ]

    violations = runtime_release_member_violations(members)

    assert "excluded_member:runtime/data/demo/state.jsonl" in violations
    assert (
        "excluded_member:rust/businessaios_safety_core/target/debug/lib.rlib"
        in violations
    )
    assert "path_traversal_member:../escape.txt" in violations
    assert "duplicate_member:main.py" in violations


def test_current_repository_release_surface_satisfies_archive_contract() -> None:
    members = [
        path.relative_to(ROOT).as_posix()
        for path in iter_runtime_release_files(ROOT)
    ]

    assert runtime_release_member_violations(members) == ()
