from __future__ import annotations

import json

import scripts.ci.step_production_boot as production_boot_step


def test_non_prod_advisory_does_not_claim_stale_ready_runtime_evidence(monkeypatch, tmp_path) -> None:
    artifact_dir = tmp_path / "artifacts" / "ci"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "real_runtime_boot_evidence.json").write_text(
        json.dumps({"artifact": "real_runtime_boot_evidence", "status": "ready"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(production_boot_step, "repo_root", lambda: tmp_path)
    monkeypatch.setenv("ENV", "ci")
    monkeypatch.setenv("APP_PROFILE", "api")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_RUNTIME_ENABLED", raising=False)
    monkeypatch.delenv("REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED", raising=False)
    monkeypatch.delenv("PRODUCTION_BOOT_PROOF_REQUIRED", raising=False)

    ok, message = production_boot_step.run()
    payload = json.loads((artifact_dir / "production_boot.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["status"] == "advisory_only"
    assert payload["proof_required"] is False
    assert payload["claims_real_runtime_boot"] is False
    assert "real_runtime_boot_evidence_source" not in payload
