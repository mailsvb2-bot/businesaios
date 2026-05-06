from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RETIRED_DECISION_IMPORTS = frozenset({
    "core.ai.policy_selector",
    "core.decision.decision_selector",
    "core.decision.decision_constraints",
    "core.policy",
    "core.policy.canary_router",
    "core.policy.router",
    "core.policy.bandit",
    "core.policy.public_api",
    "core.policy.registry",
    "core.policy.types",
    "core.growth.optimizer",
})

RETIRED_DECISION_FILES = tuple(
    Path(path)
    for path in (
        "core/ai/policy_selector.py",
        "core/decision/decision_selector.py",
        "core/decision/decision_constraints.py",
        "core/growth/optimizer.py",
        "core/policy/__init__.py",
        "core/policy/bandit.py",
        "core/policy/canary_router.py",
        "core/policy/deployer.py",
        "core/policy/domain.py",
        "core/policy/evaluator.py",
        "core/policy/metrics.py",
        "core/policy/public_api.py",
        "core/policy/registry.py",
        "core/policy/rollout.py",
        "core/policy/router.py",
        "core/policy/selector.py",
        "core/policy/shadow.py",
        "core/policy/staged_rollout.py",
        "core/policy/trainer.py",
        "core/policy/types.py",
    )
)


def imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found
