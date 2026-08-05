from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci import step_quality as quality
from scripts.ci.subprocess_io import CommandOutcome


def _outcome(*, returncode: int, stdout: str = "", stderr: str = "") -> CommandOutcome:
    return CommandOutcome(returncode=returncode, stdout=stdout, stderr=stderr)


def test_full_debt_report_groups_findings_and_writes_normalized_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "ruff.toml"
    config.write_text('target-version = "py311"\n', encoding="utf-8")
    findings = [
        {"code": "I001", "filename": str(tmp_path / "application" / "a.py"), "message": "imports"},
        {"code": "B007", "filename": str(tmp_path / "application" / "b.py"), "message": "loop"},
        {"code": "I001", "filename": str(tmp_path / "main.py"), "message": "imports"},
    ]
    observed: list[str] = []

    def run(command, **_kwargs) -> CommandOutcome:
        observed.extend(command)
        return _outcome(returncode=1, stdout=json.dumps(findings))

    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(quality, "run_command", run)

    report = quality._full_debt_report(config=config)

    assert report == {
        "full_ruff_measured": True,
        "full_ruff_total": 3,
        "full_ruff_counts_by_rule": {"B007": 1, "I001": 2},
        "full_ruff_counts_by_package": {"(root)": 1, "application": 2},
        "full_ruff_report_path": "artifacts/ci/ruff_full.json",
    }
    assert observed[3:8] == ["check", ".", "--output-format", "json", "--config"]
    payload = json.loads((tmp_path / "artifacts" / "ci" / "ruff_full.json").read_text(encoding="utf-8"))
    assert [item["filename"] for item in payload] == ["application/a.py", "application/b.py", "main.py"]


def test_full_debt_report_rejects_tool_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        quality,
        "run_command",
        lambda *_args, **_kwargs: _outcome(returncode=2, stderr="invalid config"),
    )

    report = quality._full_debt_report(config=tmp_path / "ruff.toml")

    assert report["full_ruff_measured"] is False
    assert report["full_ruff_error"] == "ruff_command_failed"
    assert report["full_ruff_returncode"] == 2
    assert not (tmp_path / "artifacts" / "ci" / "ruff_full.json").exists()


def test_full_debt_report_rejects_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        quality,
        "run_command",
        lambda *_args, **_kwargs: _outcome(returncode=1, stdout="not-json"),
    )

    assert quality._full_debt_report(config=tmp_path / "ruff.toml") == {
        "full_ruff_measured": False,
        "full_ruff_error": "ruff_json_output_parse_failed",
    }



def test_targeted_debt_failure_still_captures_full_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(quality, "_quality_target_paths", lambda _root: (tmp_path / "runtime",))
    monkeypatch.setattr(quality.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(quality, "run_command", lambda *_args, **_kwargs: _outcome(returncode=0))
    monkeypatch.setattr(
        quality,
        "_targeted_debt_report",
        lambda **_kwargs: {"targeted_strict_debt_measured": True, "targeted_strict_debt_total": 1},
    )
    measured: list[bool] = []

    def full_report(**_kwargs):
        measured.append(True)
        return {"full_ruff_measured": True, "full_ruff_total": 123}

    monkeypatch.setattr(quality, "_full_debt_report", full_report)

    ok, message, payload = quality._ruff_check()

    assert ok is False
    assert message == "targeted strict ruff debt lock failed"
    assert measured == [True]
    assert payload["full_ruff_total"] == 123
    assert payload["violations"] == ["targeted_strict_debt_lock_failed"]


def test_deployment_up035_ratchet_blocks_regressions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(quality, "_quality_target_paths", lambda _root: (tmp_path / "runtime",))
    monkeypatch.setattr(quality.importlib.util, "find_spec", lambda _name: object())
    outcomes = iter((_outcome(returncode=0), _outcome(returncode=1)))
    monkeypatch.setattr(quality, "run_command", lambda *_args, **_kwargs: next(outcomes))
    monkeypatch.setattr(quality, "_targeted_debt_report", lambda **_kwargs: {"targeted_strict_debt_measured": True, "targeted_strict_debt_total": 0})
    monkeypatch.setattr(quality, "_full_debt_report", lambda **_kwargs: {"full_ruff_measured": True, "full_ruff_total": 4877})

    ok, message, payload = quality._ruff_check()

    assert ok is False
    assert message == "deployment UP035 ruff ratchet failed"
    assert payload["deployment_up035_passed"] is False
    assert payload["violations"] == ["deployment_up035_ratchet_failed"]

def test_non_strict_quality_gate_requires_inventory_but_not_cleanliness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(quality, "_quality_target_paths", lambda _root: (tmp_path / "runtime",))
    monkeypatch.setattr(quality.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(
        quality,
        "run_command",
        lambda *_args, **_kwargs: _outcome(returncode=0),
    )
    monkeypatch.setattr(
        quality,
        "_targeted_debt_report",
        lambda **_kwargs: {"targeted_strict_debt_measured": True, "targeted_strict_debt_total": 0},
    )
    monkeypatch.setattr(
        quality,
        "_full_debt_report",
        lambda **_kwargs: {"full_ruff_measured": True, "full_ruff_total": 123},
    )
    monkeypatch.setattr(quality, "_strict_ruff_required", lambda: False)

    ok, message, payload = quality._ruff_check()

    assert ok is True
    assert "inventoried 123" in message
    assert payload["full_ruff_passed"] is False
    assert payload["status"] == "ready_with_unenforced_full_ruff"


def test_strict_quality_gate_blocks_on_inventoried_debt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(quality, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(quality, "_quality_target_paths", lambda _root: (tmp_path / "runtime",))
    monkeypatch.setattr(quality.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(
        quality,
        "run_command",
        lambda *_args, **_kwargs: _outcome(returncode=0),
    )
    monkeypatch.setattr(
        quality,
        "_targeted_debt_report",
        lambda **_kwargs: {"targeted_strict_debt_measured": True, "targeted_strict_debt_total": 0},
    )
    monkeypatch.setattr(
        quality,
        "_full_debt_report",
        lambda **_kwargs: {"full_ruff_measured": True, "full_ruff_total": 1},
    )
    monkeypatch.setattr(quality, "_strict_ruff_required", lambda: True)

    ok, message, payload = quality._ruff_check()

    assert ok is False
    assert message == "full ruff strict check failed"
    assert payload["violations"] == ["full_ruff_strict_failed"]
