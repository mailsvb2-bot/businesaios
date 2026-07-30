from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from scripts.ci import step_rust_supply_chain


def _fixture_repo(tmp_path: Path) -> Path:
    root = tmp_path
    crate = root / "rust" / "businessaios_safety_core"
    crate.mkdir(parents=True)
    (root / "rust" / "rust-toolchain.toml").write_text(
        '[toolchain]\nchannel = "1.75.0"\n',
        encoding="utf-8",
    )
    (crate / "Cargo.toml").write_text(
        '[package]\nname = "businessaios_safety_core"\nversion = "0.1.0"\nedition = "2021"\n\n'
        '[dependencies]\nserde = "1"\nserde_json = "1"\n',
        encoding="utf-8",
    )
    lock_lines = ["version = 3", ""]
    for package in sorted(step_rust_supply_chain.ALLOWED_LOCK_PACKAGES):
        lock_lines.extend(("[[package]]", f'name = "{package}"', 'version = "1.0.0"', ""))
    (crate / "Cargo.lock").write_text("\n".join(lock_lines), encoding="utf-8")
    return root


def test_cargo_audit_failure_is_written_and_exposed(monkeypatch, tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    audit_payload = {
        "vulnerabilities": {
            "found": True,
            "count": 1,
            "list": [{"advisory": {"id": "RUSTSEC-2099-0001"}}],
        },
        "warnings": {},
    }
    monkeypatch.setattr(step_rust_supply_chain, "repo_root", lambda: root)
    monkeypatch.setattr(step_rust_supply_chain.shutil, "which", lambda _name: "/usr/bin/cargo-audit")
    monkeypatch.setattr(
        step_rust_supply_chain.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout=json.dumps(audit_payload),
            stderr="audit failed",
        ),
    )

    ok, message = step_rust_supply_chain.run()
    report = json.loads(
        (root / "artifacts" / "ci" / "rust_supply_chain.json").read_text(encoding="utf-8")
    )

    assert ok is False
    assert "cargo_audit_failure_kind=vulnerabilities_found" in message
    assert "audit failed" in message
    assert report["cargo_audit_returncode"] == 1
    assert report["cargo_audit_failure_kind"] == "vulnerabilities_found"
    assert report["cargo_audit_report"] == audit_payload
    assert report["cargo_audit_stderr"] == "audit failed"


def test_cargo_audit_tool_error_remains_fail_closed(monkeypatch, tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    monkeypatch.setattr(step_rust_supply_chain, "repo_root", lambda: root)
    monkeypatch.setattr(step_rust_supply_chain.shutil, "which", lambda _name: "/usr/bin/cargo-audit")

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["cargo-audit", "audit"], timeout=180)

    monkeypatch.setattr(step_rust_supply_chain.subprocess, "run", _timeout)

    ok, message = step_rust_supply_chain.run()
    report = json.loads(
        (root / "artifacts" / "ci" / "rust_supply_chain.json").read_text(encoding="utf-8")
    )

    assert ok is False
    assert "cargo_audit_failure_kind=tool_error" in message
    assert report["cargo_audit_status"] == "failed"
    assert report["cargo_audit_failure_kind"] == "tool_error"
    assert "TimeoutExpired" in report["cargo_audit_stderr"]
