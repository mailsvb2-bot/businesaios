from __future__ import annotations

from scripts.ci.regression_impact_dotfix import blocked_artifact_paths, impacted_rules, normalize_path


def test_dot_prefixed_workflow_paths_are_preserved_and_classified() -> None:
    assert normalize_path(".github/workflows/ci.yml") == ".github/workflows/ci.yml"
    assert normalize_path("./.github/workflows/ci.yml") == ".github/workflows/ci.yml"
    assert {rule.name for rule in impacted_rules((".github/workflows/ci.yml",))} == {"ci"}


def test_dot_prefixed_cache_artifacts_are_blocked() -> None:
    assert blocked_artifact_paths((".pytest_cache/v/cache/nodeids",)) == (".pytest_cache/v/cache/nodeids",)
