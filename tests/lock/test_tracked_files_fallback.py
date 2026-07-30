from __future__ import annotations

import subprocess

import tests._infra.tracked_files as tracked_files_module
from tests._infra.tracked_files import DELIVERY_SCAN_EXCLUDED_DIRS, tracked_files


def test_tracked_files_falls_back_after_git_called_process_error(tmp_path, monkeypatch) -> None:
    top_level = tmp_path / "runtime" / "data" / "top.jsonl"
    nested = tmp_path / "runtime" / "data" / "tenant" / "events.jsonl"
    unrelated = tmp_path / "runtime" / "data" / "notes.txt"
    for path in (top_level, nested, unrelated):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    def _not_a_git_checkout(*args, **kwargs):
        raise subprocess.CalledProcessError(128, ["git", "ls-files"])

    monkeypatch.setattr(tracked_files_module.subprocess, "run", _not_a_git_checkout)

    assert tracked_files(tmp_path, "runtime/data/**/*.jsonl") == (nested, top_level)


def test_target_pathspec_is_checked_in_delivery_fallback(tmp_path, monkeypatch) -> None:
    target_file = tmp_path / "rust" / "businessaios_safety_core" / "target" / "debug" / "core.bin"
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(b"artifact")

    def _not_a_git_checkout(*args, **kwargs):
        raise subprocess.CalledProcessError(128, ["git", "ls-files"])

    monkeypatch.setattr(tracked_files_module.subprocess, "run", _not_a_git_checkout)

    assert tracked_files(
        tmp_path,
        "rust/businessaios_safety_core/target",
        fallback_excluded_dirs=DELIVERY_SCAN_EXCLUDED_DIRS - {"target"},
    ) == (target_file,)
