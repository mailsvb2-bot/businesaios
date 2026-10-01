from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci import step_quality as quality
from scripts.ci.subprocess_io import CommandOutcome


def _outcome(*, returncode: int) -> CommandOutcome:
    return CommandOutcome(returncode=returncode, stdout="", stderr="")


def test_contracts_i001_debt_cannot_regrow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ratchet = ("contracts", "I001")
    assert ratchet in quality._RATCHETED_STRICT_DEBT

    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(quality, "_quality_target_paths", lambda _root: (tmp_path / "runtime",))
    monkeypatch.setattr(quality.importlib.util, "find_spec", lambda _name: object())
    success_count = 1 + quality._RATCHETED_STRICT_DEBT.index(ratchet)
    outcomes = iter([_outcome(returncode=0)] * success_count + [_outcome(returncode=1)])
    monkeypatch.setattr(quality, "run_command", lambda *_args, **_kwargs: next(outcomes))
    monkeypatch.setattr(
        quality,
        "_targeted_debt_report",
        lambda **_kwargs: {
            "targeted_strict_debt_measured": True,
            "targeted_strict_debt_total": 0,
        },
    )
    monkeypatch.setattr(
        quality,
        "_full_debt_report",
        lambda **_kwargs: {"full_ruff_measured": True, "full_ruff_total": 4593},
    )

    ok, message, payload = quality._ruff_check()

    assert ok is False
    assert message == "contracts I001 ruff ratchet failed"
    assert payload["contracts_i001_passed"] is False
    assert payload["violations"] == ["contracts_i001_ratchet_failed"]
