from __future__ import annotations

from scripts.ci import doctor as doctor_module


def test_doctor_detects_unapproved_hook_without_sh_suffix(tmp_path, monkeypatch) -> None:
    root = tmp_path
    (root / "scripts" / "ci").mkdir(parents=True)
    (root / ".githooks").mkdir(parents=True)
    (root / ".githooks" / "post-merge").write_text("#!/usr/bin/env bash\necho drift\n", encoding="utf-8")

    monkeypatch.setattr(doctor_module, "repo_root", lambda: root)

    ok, message = doctor_module.run_doctor()

    assert not ok
    assert ".githooks/post-merge" in message
