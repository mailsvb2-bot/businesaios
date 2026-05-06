from __future__ import annotations

from pathlib import Path

import runtime.boot.boot_ml_job as mod
from runtime.boot.ml_job_defaults import (
    DEFAULT_ML_MIN_IMPROVEMENT,
    DEFAULT_ML_MIN_SAMPLE_SIZE,
    DEFAULT_ML_SOAK_PERIOD_MS,
)


class _PolicyRegistry:
    class _Ref:
        policy_id = "baseline@v1"

    def active_ref(self):
        return self._Ref()


class _DatasetBuilder:
    def __init__(self, event_store, out_dir):
        self.event_store = event_store
        self.out_dir = out_dir


class _Trainer:
    def __init__(self, registry):
        self.registry = registry


class _Validator:
    def __init__(self, *, min_improvement, min_n):
        self.min_improvement = min_improvement
        self.min_n = min_n


class _RolloutManager:
    def __init__(self, initial_policy_id):
        self.initial_policy_id = initial_policy_id


class _EventStoreAdapter:
    def __init__(self, inner):
        self.inner = inner


class _ArtifactRegistry:
    pass


def test_build_ml_job_uses_runtime_data_dir_and_safe_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "MLDatasetBuilder", _DatasetBuilder)
    monkeypatch.setattr(mod, "MLOfflineTrainer", _Trainer)
    monkeypatch.setattr(mod, "PolicyValidatorV14", _Validator)
    monkeypatch.setattr(mod, "RolloutManager", _RolloutManager)
    monkeypatch.setattr(mod, "RuntimeEventStoreAdapter", _EventStoreAdapter)
    monkeypatch.setattr(mod, "ArtifactRegistry", _ArtifactRegistry)
    monkeypatch.setattr(mod, "build_auto_deploy_guard_from_env", lambda: "guard")
    monkeypatch.setenv("BUSINESAIOS_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("ML_SNAPSHOTS_DIR", raising=False)
    monkeypatch.delenv("ML_MIN_N", raising=False)
    monkeypatch.delenv("ML_MIN_IMPROVEMENT", raising=False)
    monkeypatch.delenv("ML_SOAK_PERIOD_MS", raising=False)

    job = mod.build_ml_job(
        event_store=object(),
        core=object(),
        executor=object(),
        policy_registry=_PolicyRegistry(),
        base=Path("."),
    )

    assert str(job._builder.out_dir).endswith("ml_snapshots")
    assert job._validator.min_n == DEFAULT_ML_MIN_SAMPLE_SIZE
    assert job._validator.min_improvement == DEFAULT_ML_MIN_IMPROVEMENT
    assert job._policy_rollout_manager._soak_period_ms == DEFAULT_ML_SOAK_PERIOD_MS


def test_build_ml_job_respects_env_threshold_overrides(monkeypatch):
    monkeypatch.setattr(mod, "MLDatasetBuilder", _DatasetBuilder)
    monkeypatch.setattr(mod, "MLOfflineTrainer", _Trainer)
    monkeypatch.setattr(mod, "PolicyValidatorV14", _Validator)
    monkeypatch.setattr(mod, "RolloutManager", _RolloutManager)
    monkeypatch.setattr(mod, "RuntimeEventStoreAdapter", _EventStoreAdapter)
    monkeypatch.setattr(mod, "ArtifactRegistry", _ArtifactRegistry)
    monkeypatch.setattr(mod, "build_auto_deploy_guard_from_env", lambda: None)
    monkeypatch.setenv("ML_MIN_N", "777")
    monkeypatch.setenv("ML_MIN_IMPROVEMENT", "0.125")
    monkeypatch.setenv("ML_SOAK_PERIOD_MS", "2222")
    monkeypatch.setenv("ML_SNAPSHOTS_DIR", "/tmp/ml-test-snapshots")

    job = mod.build_ml_job(
        event_store=object(),
        core=object(),
        executor=object(),
        policy_registry=_PolicyRegistry(),
        base=Path("."),
    )

    assert job._validator.min_n == 777
    assert job._validator.min_improvement == 0.125
    assert job._policy_rollout_manager._soak_period_ms == 2222
