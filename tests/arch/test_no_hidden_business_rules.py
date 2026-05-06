import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET_FILES = [
    ROOT / "core/pricing/stop_loss.py",
    ROOT / "core/retention/feature_extractor.py",
    ROOT / "core/retention/decision_adapter.py",
    ROOT / "core/behavior/constraints.py",
    ROOT / "core/growth/strategy/signals.py",
    ROOT / "core/ai/decision_core.py",
]
SUSPECT_NAMES = {"threshold", "multiplier", "rollout", "limit"}

def _is_numeric(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float))

def test_no_magic_numbers_in_targeted_policy_assignments():
    offenders = []
    for path in TARGET_FILES:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and any(k in target.id.lower() for k in SUSPECT_NAMES) and _is_numeric(node.value):
                        offenders.append(f"{path}:{target.id}")
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                if isinstance(target, ast.Name) and any(k in target.id.lower() for k in SUSPECT_NAMES) and node.value is not None and _is_numeric(node.value):
                    offenders.append(f"{path}:{target.id}")
    assert offenders == []

def test_stop_loss_stays_on_single_canonical_surface():
    pricing = ROOT / "core/pricing"
    canonical = pricing / "stop_loss.py"
    assert canonical.exists()
    removed = ["stop_loss_rules.py", "stop_loss_window.py", "stop_loss_policy.py", "_stop_loss_compat.py"]
    for name in removed:
        assert not (pricing / name).exists(), name
