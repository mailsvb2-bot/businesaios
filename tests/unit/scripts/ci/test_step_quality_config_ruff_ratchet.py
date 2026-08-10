from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci import step_quality as quality
from scripts.ci.subprocess_io import CommandOutcome


def _outcome(*, returncode: int) -> CommandOutcome:
    return CommandOutcome(returncode=returncode, stdout="", stderr="")


def test_config_i001_ratchet_blocks_regressions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(quality, "_quality_target_paths", lambda _root: (tmp_path / "runtime",))
    monkeypatch.setattr(quality.importlib.util, "find_spec", lambda _name: object())

    def run_command(args, **_kwargs):
        is_target = str(tmp_path / "config") in args and "--select" in args and args[args.index("--select") + 1] == "I001"
        return _outcome(returncode=1 if is_target else 0)

    monkeypatch.setattr(quality, "run_command", run_command)
    monkeypatch.setattr(
        quality,
        "_targeted_debt_report",
        lambda **_kwargs: {"targeted_strict_debt_measured": True, "targeted_strict_debt_total": 0},
    )
    monkeypatch.setattr(
        quality,
        "_full_debt_report",
        lambda **_kwargs: {"full_ruff_measured": True, "full_ruff_total": 4844},
    )

    ok, message, payload = quality._ruff_check()

    assert ok is False
    assert message == "config I001 ruff ratchet failed"
    assert payload["config_i001_passed"] is False
    assert payload["violations"] == ["config_i001_ratchet_failed"]
