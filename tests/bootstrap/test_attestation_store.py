from __future__ import annotations

import json
from datetime import datetime, timezone, UTC

from runtime.bootstrap.bootstrap_attestation_store import persist_bootstrap_attestation
from runtime.bootstrap.bootstrap_contract import (
    BootstrapAttestation,
    BootstrapAttestationPolicy,
    BootstrapDiagnostics,
    BootstrapEnvironment,
    BootstrapMode,
)


def test_persist_bootstrap_attestation_writes_jsonl(tmp_path):
    env = BootstrapEnvironment(
        mode=BootstrapMode.TEST,
        project_root=tmp_path,
        runtime_dir=tmp_path / ".runtime",
        release_manifest_path=tmp_path / "manifest.json",
        strict=False,
        release_attestation_required=False,
        singleton_lock_enabled=False,
    )

    attestation = BootstrapAttestation(
        boot_id="boot-1",
        created_at=datetime.now(UTC),
        mode=BootstrapMode.TEST,
        entrypoint="runtime.bootstrap.sovereign_bootstrap.bootstrap_runtime",
        process_bootstrap_module="runtime.bootstrap",
        composition_root_module="runtime.bootstrap.runtime_composition_root",
        runtime_builder_module="runtime.bootstrap.runtime_builder",
        manifest_path=str(env.release_manifest_path),
        release_manifest_sha256=None,
        registry_fingerprint="fp-1",
        service_names=("decision_core", "observability"),
        policy=BootstrapAttestationPolicy(),
        diagnostics=BootstrapDiagnostics(
            registry_service_names=("decision_core", "observability"),
            report_service_names=("decision_core", "observability"),
            runtime_builder_module="runtime.bootstrap.runtime_builder",
            composition_root_module="runtime.bootstrap.runtime_composition_root",
            warnings=(),
        ),
    )

    path = persist_bootstrap_attestation(env=env, attestation=attestation)
    line = path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)

    assert payload["boot_id"] == "boot-1"
    assert payload["policy"]["contract_version"].startswith("sovereign-bootstrap-")
