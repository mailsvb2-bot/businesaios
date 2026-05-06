from __future__ import annotations

from scripts.ci.config import project_shape_config
from scripts.ci.paths import repo_root


def test_ci_config_uses_canonical_marker_expressions() -> None:
    cfg = project_shape_config(repo_root())
    assert cfg.unit_mark_expression == "not slow and not integration and not gate"
    assert cfg.integration_mark_expression == "not slow and not gate"
    assert cfg.lock_mark_expression == "not slow"
