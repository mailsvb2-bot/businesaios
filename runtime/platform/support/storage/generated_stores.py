"""Canonical named store owner for platform-support storage surfaces.

Prevents file-per-store fan-out where dozens of modules only defined an empty
subclass of one of the two base store types.
"""

from __future__ import annotations


from runtime.platform.support.storage.base_stores import ArtifactStore, DatasetStore

_STORE_SPECS: dict[str, tuple[str, type]] = {
    "CheckpointStore": ("checkpoint_store", ArtifactStore),
    "EvaluationStore": ("evaluation_store", ArtifactStore),
    "ModelArtifactStore": ("model_artifact_store", ArtifactStore),
    "PackagingStore": ("packaging_store", ArtifactStore),
    "ReportStore": ("report_store", ArtifactStore),
    "SignatureStore": ("signature_store", ArtifactStore),
    "BenchmarkStore": ("benchmark_store", DatasetStore),
    "PreferenceStore": ("preference_store", DatasetStore),
    "ReplayStore": ("replay_store", DatasetStore),
    "RolloutStore": ("rollout_store", DatasetStore),
    "SimulationStore": ("simulation_store", DatasetStore),
    "AuditStore": ("audit_store", ArtifactStore),
    "CandidateRegistryStore": ("candidate_registry_store", ArtifactStore),
    "EvaluationRegistryStore": ("evaluation_registry_store", ArtifactStore),
    "ExperimentRegistryStore": ("experiment_registry_store", ArtifactStore),
    "LineageStore": ("lineage_store", ArtifactStore),
    "PolicyRegistryStore": ("policy_registry_store", ArtifactStore),
    "RolloutRegistryStore": ("rollout_registry_store", ArtifactStore),
}


def _make_store_type(name: str, base: type) -> type:
    cls = type(name, (base,), {})
    cls.__module__ = __name__
    return cls


STORE_TYPES: dict[str, type[object]] = {
    name: _make_store_type(name, base)
    for name, (_, base) in _STORE_SPECS.items()
}

globals().update(STORE_TYPES)


def store_type(name: str) -> type:
    return STORE_TYPES[name]


def module_basename(name: str) -> str:
    return _STORE_SPECS[name][0]


def exported_names() -> tuple[str, ...]:
    return tuple(_STORE_SPECS)


__all__ = [*STORE_TYPES.keys(), 'STORE_TYPES', 'store_type', 'module_basename', 'exported_names']
