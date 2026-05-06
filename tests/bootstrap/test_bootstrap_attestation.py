from __future__ import annotations

from dataclasses import dataclass

from runtime.bootstrap.bootstrap_attestation import build_bootstrap_attestation
from runtime.bootstrap.bootstrap_contract import (
    BootstrapArtifacts,
    BootstrapAttestationPolicy,
    BootstrapEnvironment,
    BootstrapMode,
)


class _FakeSnapshot:
    def __init__(self, service_names):
        self.service_names = tuple(service_names)


class _FakeRegistry:
    def snapshot(self):
        return _FakeSnapshot(["decision_core", "executor", "observability"])


class _FakeReport:
    def service_names(self):
        return ("decision_core", "executor", "observability")


@dataclass(frozen=True)
class _FakeFingerprint:
    value: str = "fingerprint-123"


def test_bootstrap_attestation_contains_manifest_hash(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version":"1"}', encoding="utf-8")

    env = BootstrapEnvironment(
        mode=BootstrapMode.TEST,
        project_root=tmp_path,
        runtime_dir=tmp_path / ".runtime",
        release_manifest_path=manifest,
        strict=False,
        release_attestation_required=True,
        singleton_lock_enabled=False,
    )
    artifacts = BootstrapArtifacts(
        registry=_FakeRegistry(),
        report=_FakeReport(),
        exports=object(),
        fingerprint=_FakeFingerprint(),
        built_runtime=object(),
    )

    attestation = build_bootstrap_attestation(
        env=env,
        artifacts=artifacts,
        policy=BootstrapAttestationPolicy(),
    )

    assert attestation.release_manifest_sha256
    assert attestation.registry_fingerprint == "fingerprint-123"
    assert attestation.service_names == (
        "decision_core",
        "executor",
        "observability",
    )
    assert attestation.diagnostics.registry_service_names == attestation.diagnostics.report_service_names
    assert attestation.policy.contract_version.startswith("sovereign-bootstrap-")


def test_bootstrap_attestation_warns_when_manifest_missing(tmp_path):
    env = BootstrapEnvironment(
        mode=BootstrapMode.TEST,
        project_root=tmp_path,
        runtime_dir=tmp_path / ".runtime",
        release_manifest_path=tmp_path / "missing-manifest.json",
        strict=False,
        release_attestation_required=True,
        singleton_lock_enabled=False,
    )
    artifacts = BootstrapArtifacts(
        registry=_FakeRegistry(),
        report=_FakeReport(),
        exports=object(),
        fingerprint=_FakeFingerprint(),
        built_runtime=object(),
    )

    attestation = build_bootstrap_attestation(
        env=env,
        artifacts=artifacts,
        policy=BootstrapAttestationPolicy(),
    )

    assert attestation.release_manifest_sha256 is None
    assert "manifest_hash_missing" in attestation.diagnostics.warnings
