from __future__ import annotations

import json

import pytest

from runtime.boot.phase_policy_registry import _PolicyRuntimeStateFileStore


def test_policy_runtime_state_file_store_uses_generation_cas(tmp_path) -> None:
    path = tmp_path / "governance" / "policy_runtime_state.json"
    store = _PolicyRuntimeStateFileStore(path)
    first = {"schema_version": 1, "rollout_generation": 1, "lifecycle": {}}
    store.save(first, expected_generation=0)
    assert dict(store.load() or {}) == first

    with pytest.raises(RuntimeError, match="GENERATION_CONFLICT"):
        store.save(
            {"schema_version": 1, "rollout_generation": 2, "lifecycle": {}},
            expected_generation=0,
        )
    assert dict(store.load() or {}) == first


def test_policy_runtime_state_file_store_fails_closed_on_corrupt_json(tmp_path) -> None:
    path = tmp_path / "governance" / "policy_runtime_state.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _PolicyRuntimeStateFileStore(path).load()
