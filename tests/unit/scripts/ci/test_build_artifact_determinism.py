from __future__ import annotations

import os
import zipfile
from pathlib import Path

from scripts.ci import step_build_artifact


def _write(root: Path, rel: str, value: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def test_release_zip_is_deterministic_clean_and_keeps_cargo_lock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    required = {
        "Dockerfile": "FROM scratch\n",
        "VERSION": "1.2.3\n",
        "main.py": "print('ok')\n",
        "requirements.release.lock.txt": "example==1 --hash=sha256:abc\n",
        "rust/businessaios_safety_core/Cargo.lock": "version = 3\n",
    }
    for rel, value in required.items():
        _write(tmp_path, rel, value)
    source = _write(tmp_path, "application/service.py", "VALUE = 1\n")
    _write(tmp_path, "runtime/data/demo/leak.jsonl", "secret state\n")
    _write(tmp_path, "rust/businessaios_safety_core/target/debug/junk", "junk")

    monkeypatch.setattr(step_build_artifact, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_build_artifact, "dist_dir", lambda: dist)
    monkeypatch.setattr(step_build_artifact, "_version", lambda: "1.2.3")

    ok_first, _ = step_build_artifact.run()
    first = (dist / "BUSINESAIOS_1.2.3_release.zip").read_bytes()
    os.utime(source, (2_000_000_000, 2_000_000_000))
    ok_second, _ = step_build_artifact.run()
    second = (dist / "BUSINESAIOS_1.2.3_release.zip").read_bytes()

    assert ok_first is True
    assert ok_second is True
    assert first == second

    with zipfile.ZipFile(dist / "BUSINESAIOS_1.2.3_release.zip") as archive:
        members = archive.namelist()
        assert "rust/businessaios_safety_core/Cargo.lock" in members
        assert "runtime/data/demo/leak.jsonl" not in members
        assert not any("/target/" in member for member in members)
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
