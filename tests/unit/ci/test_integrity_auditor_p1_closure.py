from __future__ import annotations

from pathlib import Path

from scripts.ci.integrity import auditor


def test_documented_canonical_alias_groups_do_not_emit_naming_drift() -> None:
    spec = auditor.load_spec()
    findings = auditor.check_naming_synonyms(auditor.iter_python_files(), spec)
    assert [finding.check_id for finding in findings] == []


def test_telegram_runner_helpers_do_not_import_runtime_boot_env() -> None:
    path = Path("interfaces/telegram/runner_helpers.py")
    text = path.read_text(encoding="utf-8")

    assert "from runtime.boot.env import" not in text
    assert "from runtime.platform.config.env_access import env_float, env_int" in text
