from __future__ import annotations

import json

from runtime.platform.support._command_surface import run_named_command


def test_run_named_command_strict_mode_fails_closed_for_missing_implementation(tmp_path, monkeypatch, capsys) -> None:
    audit_path = tmp_path / "command-audit.jsonl"
    monkeypatch.setenv("BUSINESAIOS_COMMAND_AUDIT_PATH", str(audit_path))
    monkeypatch.setenv("BUSINESAIOS_PLATFORM_SUPPORT_STRICT_ENTRYPOINTS", "1")

    exit_code = run_named_command(surface="cli", command="train")

    assert exit_code == 78
    assert "strict failure" in capsys.readouterr().err
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"command": "train", "exit_code": 78, "implemented": False, "surface": "cli"}]
