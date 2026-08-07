from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci import step_quality as quality
from scripts.ci.subprocess_io import CommandOutcome


def _outcome(*, returncode: int) -> CommandOutcome:
    return CommandOutcome(returncode=returncode, stdout="", stderr="")


def test_release_i001_ratchet_blocks_regressions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(quality, "_quality_target_paths", lambda _root: (tmp_path / "runtime",))
    monkeypatch.setattr(quality.importlib.util, "find_spec", lambda _name: object())
    outcomes = iter([_outcome(returncode=0)] * 16 + [_outcome(returncode=1)])
    monkeypatch.setattr(quality, "run_command", lambda *_args, **_kwargs: next(outcomes))
    monkeypatch.setattr(
        quality,
        "_targeted_debt_report",
        lambda **_kwargs: {"targeted_strict_debt_measured": True, "targeted_strict_debt_total": 0},
    )
    monkeypatch.setattr(
        quality,
        "_full_debt_report",
        lambda **_kwargs: {"full_ruff_measured": True, "full_ruff_total": 4852},
    )

    ok, message, payload = quality._ruff_check()

    assert ok is False
    assert message == "release I001 ruff ratchet failed"
    assert payload["release_i001_passed"] is False
    assert payload["violations"] == ["release_i001_ratchet_failed"]
