from __future__ import annotations

from pathlib import Path

from scripts.ci import doctor as doctor_module


def test_doctor_detects_second_execution_import(tmp_path, monkeypatch) -> None:
    root = tmp_path
    ci_root = root / "scripts" / "ci"
    ci_root.mkdir(parents=True, exist_ok=True)

    (ci_root / "execution.py").write_text("x = 1\n", encoding="utf-8")
    (ci_root / "rogue.py").write_text(
        "from scripts.ci.execution import execute\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(doctor_module, "repo_root", lambda: root)

    ok, message = doctor_module.run_doctor()
    assert ok is False
    assert "second execution path detected" in message
