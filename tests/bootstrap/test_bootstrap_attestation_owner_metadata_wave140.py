from __future__ import annotations

from pathlib import Path

from runtime.bootstrap.bootstrap_attestation import build_bootstrap_attestation
from runtime.bootstrap.bootstrap_contract import (
    BootstrapArtifacts,
    BootstrapAttestationPolicy,
    BootstrapEnvironment,
    BootstrapMode,
)


class _Snapshot:
    service_names = ("decision_core", "observability")


class _Registry:
    def snapshot(self):
        return _Snapshot()


class _Report:
    def service_names(self):
        return ("decision_core", "observability")


class _Fingerprint:
    value = "fp-1"


def test_bootstrap_attestation_uses_canonical_bootstrap_owner_metadata(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    env = BootstrapEnvironment(
        mode=BootstrapMode.TEST,
        project_root=tmp_path,
        runtime_dir=tmp_path / ".runtime",
        release_manifest_path=manifest,
        strict=False,
        release_attestation_required=False,
        singleton_lock_enabled=False,
    )
    artifacts = BootstrapArtifacts(
        registry=_Registry(),
        report=_Report(),
        exports=object(),
        fingerprint=_Fingerprint(),
        built_runtime=object(),
    )

    attestation = build_bootstrap_attestation(
        env=env,
        artifacts=artifacts,
        policy=BootstrapAttestationPolicy(),
    )

    assert attestation.entrypoint == "runtime.bootstrap.sovereign_bootstrap.bootstrap_runtime"
    assert attestation.process_bootstrap_module == "runtime.bootstrap"
    assert attestation.runtime_builder_module == "runtime.bootstrap.runtime_builder"
    assert attestation.composition_root_module == "runtime.bootstrap.runtime_composition_root"
    assert attestation.diagnostics.runtime_builder_module == "runtime.bootstrap.runtime_builder"
    assert attestation.diagnostics.composition_root_module == "runtime.bootstrap.runtime_composition_root"


def test_bootstrap_attestation_builder_source_declares_bootstrap_owner_metadata() -> None:
    text = Path("runtime/bootstrap/bootstrap_attestation.py").read_text(encoding="utf-8")
    assert 'runtime.bootstrap.runtime_builder' in text
    assert 'runtime.bootstrap.runtime_composition_root' in text
    assert 'runtime.bootstrap_pkg.runtime_builder' not in text
