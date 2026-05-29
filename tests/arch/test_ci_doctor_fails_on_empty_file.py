from __future__ import annotations

from scripts.ci import doctor as doctor_module


def test_doctor_detects_empty_ci_file(tmp_path, monkeypatch) -> None:
    root = tmp_path
    ci_root = root / "scripts" / "ci"
    ci_root.mkdir(parents=True, exist_ok=True)
    (ci_root / "empty.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(doctor_module, "repo_root", lambda: root)

    ok, message = doctor_module.run_doctor()
    assert ok is False
    assert "empty ci files detected" in message
