from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import step_verify_release


_REQUIRED_READY_PAYLOADS = {
    "postgres_contract.json": {
        "artifact": "postgres_contract",
        "status": "ready",
        "claims_production_ready": False,
    },
    "postgres_migrations.json": {
        "artifact": "postgres_migrations",
        "status": "ready",
        "claims_production_ready": False,
    },
    "postgres_live.json": {
        "artifact": "postgres_live",
        "status": "ready",
        "claims_production_ready": False,
    },
    "container_runtime.json": {
        "artifact": "container_runtime",
        "status": "ready",
        "claims_production_ready": False,
    },
    "staging_runtime_proof.json": {
        "artifact": "staging_runtime_proof",
        "status": "ready",
        "claims_production_ready": False,
    },
    "production_boot.json": {
        "artifact": "production_boot_contract",
        "status": "contract_satisfied",
        "claims_production_ready": False,
    },
}


def _artifact_dir() -> Path:
    path = step_verify_release.repo_root() / "artifacts" / "ci"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clear_verify_release_test_artifacts() -> None:
    directory = _artifact_dir()
    for name in (*_REQUIRED_READY_PAYLOADS, "verify_release.json"):
        path = directory / name
        if path.exists():
            path.unlink()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write_required_ready_artifacts() -> None:
    directory = _artifact_dir()
    for name, payload in _REQUIRED_READY_PAYLOADS.items():
        _write_json(directory / name, payload)


def test_verify_release_blocks_when_required_proof_artifact_is_missing() -> None:
    _clear_verify_release_test_artifacts()

    ok, message = step_verify_release._aggregate_required_proof_artifacts()
    payload = _read_json(_artifact_dir() / "verify_release.json")

    assert ok is False
    assert "postgres_contract_not_ready" in message
    assert payload["status"] == "blocked"
    assert "postgres_contract_not_ready" in payload["violations"]
    assert payload["claims_production_ready"] is False


def test_verify_release_accepts_complete_ready_proof_artifact_set() -> None:
    _clear_verify_release_test_artifacts()
    _write_required_ready_artifacts()

    ok, message = step_verify_release._aggregate_required_proof_artifacts()
    payload = _read_json(_artifact_dir() / "verify_release.json")

    assert ok is True, message
    assert payload["status"] == "ready"
    assert payload["violations"] == []
    assert payload["claims_production_ready"] is False


def test_verify_release_rejects_premature_production_ready_claims() -> None:
    _clear_verify_release_test_artifacts()
    _write_required_ready_artifacts()
    path = _artifact_dir() / "postgres_live.json"
    payload = _read_json(path)
    payload["claims_production_ready"] = True
    _write_json(path, payload)

    ok, message = step_verify_release._aggregate_required_proof_artifacts()
    report = _read_json(_artifact_dir() / "verify_release.json")

    assert ok is False
    assert "postgres_live_must_not_claim_production_ready" in message
    assert "postgres_live_must_not_claim_production_ready" in report["violations"]
