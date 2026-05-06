from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_runtime_messaging_policy_no_llm_in_runtime_effects() -> None:
    hits = scan_lines(
        patterns={
            "llm_in_messaging_effects": r"llm_(prompt|ranker|strategy)|world_model_score|decision_score",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_runtime_effects_no_llm_policy.py",
        ),
        root=REPO_ROOT / "runtime" / "_internal" / "effects_actions" / "telegram",
    )
    assert not hits, (
        "Runtime messaging effects must not reintroduce semantic decision logic.\n"
        + format_hits(hits)
    )
