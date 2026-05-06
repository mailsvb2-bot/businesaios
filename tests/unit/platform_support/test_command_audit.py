from __future__ import annotations

import json

from runtime.platform.support._command_surface import run_named_command
from runtime.platform.support.command_audit import build_command_audit_record


def test_build_command_audit_record_is_structured() -> None:
    assert build_command_audit_record(surface="cli", command="train", implemented=False, exit_code=0) == {
        "surface": "cli",
        "command": "train",
        "implemented": False,
        "exit_code": 0,
    }


def test_run_named_command_emits_audit_file_for_stub(tmp_path, monkeypatch, capsys) -> None:
    audit_path = tmp_path / "command-audit.jsonl"
    monkeypatch.setenv("BUSINESAIOS_COMMAND_AUDIT_PATH", str(audit_path))

    exit_code = run_named_command(surface="cli", command="train")

    assert exit_code == 0
    assert "no bundled implementation" in capsys.readouterr().err
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"command": "train", "exit_code": 0, "implemented": False, "surface": "cli"}]


def test_run_named_command_emits_audit_file_for_implemented_handler(tmp_path, monkeypatch) -> None:
    audit_path = tmp_path / "command-audit.jsonl"
    monkeypatch.setenv("BUSINESAIOS_COMMAND_AUDIT_PATH", str(audit_path))

    exit_code = run_named_command(
        surface="script",
        command="rebuild_lineage",
        implementations={"rebuild_lineage": lambda: 7},
    )

    assert exit_code == 7
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"command": "rebuild_lineage", "exit_code": 7, "implemented": True, "surface": "script"}]
