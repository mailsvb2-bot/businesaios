from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.ci import exact_head_proof as proof


def _repo(tmp_path: Path) -> tuple[Path, str]:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "ci@example.test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "CI"],
        check=True,
    )
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("ok\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "initial"],
        check=True,
    )
    sha = subprocess.check_output(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(tmp_path), "branch", "-f", "main", sha],
        check=True,
    )
    return tmp_path, sha


def _success_command(**kwargs) -> proof.CommandResult:
    return proof.CommandResult(
        name=str(kwargs["name"]),
        command=tuple(kwargs["command"]),
        returncode=0,
        duration_ms=1,
    )


def test_exact_head_proof_writes_machine_readable_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, sha = _repo(tmp_path)
    monkeypatch.setattr(proof, "_run_command", _success_command)
    report_path = repo / "proof.json"

    report = proof.run_exact_head_proof(
        repo=repo,
        expected_sha=sha,
        gates=("fast", "full"),
        target_base="main",
        report_path=report_path,
    )

    assert report.success is True
    assert [item.name for item in report.commands] == [
        "requirements-lock",
        "fast",
        "full",
    ]
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["head_sha"] == sha
    assert payload["expected_sha"] == sha
    assert payload["target_base_sha"] == sha
    assert payload["success"] is True


def test_exact_head_proof_rejects_dirty_worktree(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(proof.ExactHeadProofError, match="not clean"):
        proof.run_exact_head_proof(
            repo=repo,
            expected_sha=sha,
            gates=("fast",),
            target_base="main",
        )


def test_exact_head_proof_rejects_sha_mismatch(tmp_path: Path) -> None:
    repo, _sha = _repo(tmp_path)

    with pytest.raises(proof.ExactHeadProofError, match="HEAD mismatch"):
        proof.run_exact_head_proof(
            repo=repo,
            expected_sha="0" * 40,
            gates=("fast",),
            target_base="main",
        )


def test_fail_fast_stops_after_first_failed_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, sha = _repo(tmp_path)

    def run(**kwargs) -> proof.CommandResult:
        name = str(kwargs["name"])
        return proof.CommandResult(
            name=name,
            command=tuple(kwargs["command"]),
            returncode=1 if name == "fast" else 0,
            duration_ms=1,
        )

    monkeypatch.setattr(proof, "_run_command", run)
    report = proof.run_exact_head_proof(
        repo=repo,
        expected_sha=sha,
        gates=("fast", "full"),
        target_base="main",
        report_path=repo / "proof.json",
        fail_fast=True,
    )

    assert report.success is False
    assert [item.name for item in report.commands] == [
        "requirements-lock",
        "fast",
    ]


def test_relative_report_path_is_resolved_inside_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, sha = _repo(tmp_path)
    monkeypatch.setattr(proof, "_run_command", _success_command)

    proof.run_exact_head_proof(
        repo=repo,
        expected_sha=sha,
        gates=("fast",),
        target_base="main",
        report_path=Path("artifacts/ci/proof.json"),
    )

    assert (repo / "artifacts" / "ci" / "proof.json").is_file()
