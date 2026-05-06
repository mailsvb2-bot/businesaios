from __future__ import annotations

"""Canonical owner for generated registry store compatibility surfaces."""

from runtime.platform.support.storage.generated_stores import (
    AuditStore,
    CandidateRegistryStore,
    EvaluationRegistryStore,
    ExperimentRegistryStore,
    LineageStore,
    PolicyRegistryStore,
    RolloutRegistryStore,
)

_ALIAS_EXPORTS = {
    "audit_store": "AuditStore",
    "candidate_registry_store": "CandidateRegistryStore",
    "evaluation_registry_store": "EvaluationRegistryStore",
    "experiment_registry_store": "ExperimentRegistryStore",
    "lineage_store": "LineageStore",
    "policy_registry_store": "PolicyRegistryStore",
    "rollout_registry_store": "RolloutRegistryStore",
}

__all__ = [
    "AuditStore",
    "CandidateRegistryStore",
    "EvaluationRegistryStore",
    "ExperimentRegistryStore",
    "LineageStore",
    "PolicyRegistryStore",
    "RolloutRegistryStore",
]
