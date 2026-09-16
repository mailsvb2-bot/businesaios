from __future__ import annotations

from runtime.business_autonomy.provider_runtime_audit import ProviderRuntimeAuditRecorder
from storage.audit_wiring import build_canonical_audit_store
from storage.distributed_evidence_audit_backend import (
    LegacyDistributedEvidenceMigrationPort,
    migrate_legacy_distributed_evidence,
)
from storage.evidence_store import EvidenceStore
from storage.evidence_wiring import build_canonical_evidence_store


def build_business_autonomy_evidence_store(
    *, legacy_source: LegacyDistributedEvidenceMigrationPort
) -> EvidenceStore:
    store = build_canonical_evidence_store()
    migrate_legacy_distributed_evidence(source=legacy_source, target=store)
    return store


def build_provider_runtime_audit_recorder() -> ProviderRuntimeAuditRecorder:
    return ProviderRuntimeAuditRecorder(
        audit_store=build_canonical_audit_store(),
        evidence_store=build_canonical_evidence_store(),
    )


__all__ = [
    "build_business_autonomy_evidence_store",
    "build_provider_runtime_audit_recorder",
]
