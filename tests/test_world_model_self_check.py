from __future__ import annotations

from pathlib import Path

import pytest

import bootstrap.world_model_self_check as self_check
from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel


class DummyStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        return None


def _world_model() -> CanonicalDecisionWorldModel:
    return CanonicalDecisionWorldModel(store=DummyStore(), kind="hybrid@v1")


def test_runtime_self_check_does_not_walk_checkout_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fail_if_scanned(*, repo_root):
        raise AssertionError(f"runtime boot must not scan repository source: {repo_root}")

    monkeypatch.setattr(
        self_check,
        "scan_repo_for_forbidden_world_model_paths",
        fail_if_scanned,
    )

    result = self_check.run_world_model_self_check(
        world_model=_world_model(),
        repo_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["source_scan_enabled"] is False
    assert result["forbidden_paths"] == []


def test_explicit_runtime_source_scan_remains_fail_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from core.economics.ltv_world_model import WorldModel\n"
        "x = WorldModel(LTVModel())\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("STRICT_WORLD_MODEL_SELF_CHECK", "1")

    with pytest.raises(self_check.WorldModelSelfCheckError):
        self_check.run_world_model_self_check(
            world_model=_world_model(),
            repo_root=tmp_path,
            scan_source=True,
        )
