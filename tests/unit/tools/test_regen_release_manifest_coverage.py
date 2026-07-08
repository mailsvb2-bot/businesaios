from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from tools import regen_release_manifest as regen


def test_sha256_file_reads_file_in_chunks(tmp_path: Path) -> None:
    target = tmp_path / "payload.bin"
    target.write_bytes(b"abc" * 5000)

    assert regen.sha256_file(target) == hashlib.sha256(b"abc" * 5000).hexdigest()


def test_main_rejects_missing_manifest(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(regen, "MANIFEST_PATH", tmp_path / "release/manifest.json")
    monkeypatch.setattr(sys, "argv", ["regen_release_manifest"])

    assert regen.main() == 2
    assert "release/manifest.json not found" in capsys.readouterr().err


def test_main_rejects_non_dict_files(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "release/manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"files": ["not-a-dict"]}), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(regen, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(sys, "argv", ["regen_release_manifest"])

    assert regen.main() == 2
    assert "manifest.files must be a dict" in capsys.readouterr().err


def test_main_reports_matching_manifest(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = tmp_path / "payload.txt"
    payload.write_text("hello", encoding="utf-8")
    digest = regen.sha256_file(payload)

    manifest = tmp_path / "release/manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"files": {"payload.txt": digest}}), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(regen, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(sys, "argv", ["regen_release_manifest"])

    assert regen.main() == 0
    assert "OK: manifest matches files" in capsys.readouterr().out


def test_main_detects_diff_and_can_write_manifest(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = tmp_path / "payload.txt"
    payload.write_text("new", encoding="utf-8")

    manifest = tmp_path / "release/manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps({"files": {"payload.txt": "oldhash", "missing.txt": "gone"}}),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(regen, "MANIFEST_PATH", manifest)

    monkeypatch.setattr(sys, "argv", ["regen_release_manifest", "--fail-on-diff"])
    assert regen.main() == 1
    assert "DIFF payload.txt" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["regen_release_manifest", "--write"])
    assert regen.main() == 0

    out = capsys.readouterr().out
    assert "WROTE: updated manifest.json" in out

    updated = json.loads(manifest.read_text(encoding="utf-8"))
    assert updated["files"]["payload.txt"] == regen.sha256_file(payload)
    assert updated["files"]["missing.txt"] == "gone"
