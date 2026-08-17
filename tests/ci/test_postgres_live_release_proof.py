from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from runtime.platform import postgres_live_probe
from scripts.ci import step_postgres_live

_EXACT_SHA = "a" * 40
_OTHER_SHA = "b" * 40


def _configure_backup_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    evidence_commit_sha: str = _EXACT_SHA,
    dump_sha256: str | None = None,
) -> Path:
    artifact_root = tmp_path / "artifacts" / "ci"
    artifact_root.mkdir(parents=True, exist_ok=True)
    dump_path = artifact_root / "postgres-backup.dump"
    dump_path.write_bytes(b"canonical-postgres-backup")
    digest = dump_sha256 or hashlib.sha256(dump_path.read_bytes()).hexdigest()
    evidence_path = artifact_root / "postgres-backup-restore-evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "contract": step_postgres_live._BACKUP_EVIDENCE_CONTRACT,
                "commit_sha": evidence_commit_sha,
                "dump_path": "artifacts/ci/postgres-backup.dump",
                "dump_sha256": digest,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(step_postgres_live, "repo_root", lambda: tmp_path)
    monkeypatch.setenv("GIT_COMMIT_SHA", _EXACT_SHA)
    monkeypatch.delenv("BAIOS_CI_TARGET_SHA", raising=False)
    monkeypatch.setenv(
        "POSTGRES_BACKUP_EVIDENCE_PATH",
        "artifacts/ci/postgres-backup-restore-evidence.json",
    )
    monkeypatch.setenv("POSTGRES_RESTORE_DSN", "postgresql://restore-proof")
    return evidence_path


class _RestorePort:
    restored_sha = _EXACT_SHA

    def __init__(self, dsn: str, *, application_name: str) -> None:
        assert dsn == "postgresql://restore-proof"
        assert application_name == "businesaios-postgres-backup-restore-proof"

    def __enter__(self) -> _RestorePort:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def fetchone(self, query: str, params: tuple[int]) -> tuple[str]:
        assert query == step_postgres_live._BACKUP_SENTINEL_QUERY
        assert params == (1,)
        return (self.restored_sha,)


@pytest.mark.parametrize(
    "invalid_sha",
    (
        "a" * 39,
        "A" * 40,
        "g" * 40,
        "a" * 41,
    ),
)
def test_backup_evidence_rejects_noncanonical_expected_sha(
    monkeypatch: pytest.MonkeyPatch,
    invalid_sha: str,
) -> None:
    monkeypatch.setenv("GIT_COMMIT_SHA", invalid_sha)
    monkeypatch.delenv("BAIOS_CI_TARGET_SHA", raising=False)

    assert step_postgres_live._backup_evidence_status() == (
        False,
        "postgres_backup_expected_commit_sha_invalid",
    )


def test_backup_evidence_requires_ci_artifact_confinement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = tmp_path / "outside-evidence.json"
    outside.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(step_postgres_live, "repo_root", lambda: tmp_path)
    monkeypatch.setenv("GIT_COMMIT_SHA", _EXACT_SHA)
    monkeypatch.setenv("POSTGRES_BACKUP_EVIDENCE_PATH", str(outside))

    assert step_postgres_live._backup_evidence_status() == (
        False,
        "postgres_backup_evidence_path_required",
    )


def test_backup_evidence_rejects_different_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_backup_evidence(tmp_path, monkeypatch, evidence_commit_sha=_OTHER_SHA)

    assert step_postgres_live._backup_evidence_status() == (
        False,
        "postgres_backup_evidence_commit_sha_mismatch",
    )


def test_backup_evidence_rejects_noncanonical_evidence_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_backup_evidence(tmp_path, monkeypatch, evidence_commit_sha=_EXACT_SHA.upper())

    assert step_postgres_live._backup_evidence_status() == (
        False,
        "postgres_backup_evidence_commit_sha_invalid",
    )


def test_backup_evidence_rejects_dump_digest_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_backup_evidence(tmp_path, monkeypatch, dump_sha256="0" * 64)

    assert step_postgres_live._backup_evidence_status() == (
        False,
        "postgres_backup_dump_sha256_mismatch",
    )


def test_backup_evidence_requires_restored_exact_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_backup_evidence(tmp_path, monkeypatch)

    class WrongRestorePort(_RestorePort):
        restored_sha = _OTHER_SHA

    monkeypatch.setattr(step_postgres_live, "PostgresPort", WrongRestorePort)

    assert step_postgres_live._backup_evidence_status() == (
        False,
        "postgres_backup_restore_commit_sha_mismatch",
    )


def test_backup_evidence_accepts_exact_dump_and_restored_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_backup_evidence(tmp_path, monkeypatch)
    monkeypatch.setattr(step_postgres_live, "PostgresPort", _RestorePort)

    assert step_postgres_live._backup_evidence_status() == (
        True,
        "postgres_backup_restore_verified",
    )


class _MainProbePort:
    def __init__(self, _dsn: str, *, application_name: str) -> None:
        assert application_name == "businesaios-postgres-live"

    def __enter__(self) -> _MainProbePort:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def ping(self) -> bool:
        return True


@pytest.mark.parametrize(
    ("concurrency_ok", "expected_outbox_ok"),
    ((False, False), (True, True)),
)
def test_postgres_live_requires_concurrency_for_outbox_proof(
    monkeypatch: pytest.MonkeyPatch,
    concurrency_ok: bool,
    expected_outbox_ok: bool,
) -> None:
    captured_proofs = []

    def capture_contract(proof):
        captured_proofs.append(proof)
        return {
            "status": "ready" if proof.outbox_roundtrip_ok else "blocked",
            "violations": [],
        }

    monkeypatch.setattr(postgres_live_probe, "PostgresPort", _MainProbePort)
    monkeypatch.setattr(postgres_live_probe, "_schema_objects", lambda _port: ("runtime_outbox",))
    monkeypatch.setattr(postgres_live_probe, "_migrations", lambda _port: ())
    monkeypatch.setattr(postgres_live_probe, "_outbox_roundtrip", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        postgres_live_probe,
        "_outbox_concurrent_idempotency_roundtrip",
        lambda *_args, **_kwargs: concurrency_ok,
    )
    monkeypatch.setattr(postgres_live_probe, "evaluate_postgres_contract", capture_contract)

    payload = postgres_live_probe.run_postgres_live_probe(
        postgres_live_probe.PostgresLiveProbeConfig(
            dsn="postgresql://live-proof",
            backup_evidence_ok=True,
        )
    )

    assert captured_proofs[-1].outbox_roundtrip_ok is expected_outbox_ok
    assert payload["outbox_state_transition_ok"] is True
    assert payload["outbox_concurrent_idempotency_ok"] is concurrency_ok
