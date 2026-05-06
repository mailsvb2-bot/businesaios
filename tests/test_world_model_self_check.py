from __future__ import annotations

from pathlib import Path

from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
from bootstrap.world_model_self_check import run_world_model_self_check


class DummyStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        return None


def test_run_world_model_self_check_ok(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text("print('ok')\n", encoding="utf-8")

    wm = CanonicalDecisionWorldModel(store=DummyStore(), kind="hybrid@v1")
    result = run_world_model_self_check(
        world_model=wm,
        repo_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["forbidden_paths"] == []
