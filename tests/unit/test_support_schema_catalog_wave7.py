from __future__ import annotations

from runtime.platform.support.schemas.python.checkpoint_schema import checkpoint_schema
from runtime.platform.support.schemas.python.transition_schema import transition_schema
from runtime.platform.support.schemas.validators.checkpoint_validator import valid_checkpoint
from runtime.platform.support.schemas.validators.rollout_validator import valid_rollout


def test_schema_catalog_preserves_legacy_import_paths() -> None:
    assert checkpoint_schema()["required"] == ["uri"]
    assert transition_schema()["required"] == ["observation", "action", "reward", "done"]
    assert valid_checkpoint({"uri": "x"}) is True
    assert valid_rollout({"rollout_id": "r1", "episodes": []}) is True
    assert valid_rollout({"rollout_id": "r1"}) is False
