from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_OWNER = "core/llm/model_runtime.py"
OWNED_CLASSES = (
    "ModelCapabilityRegistry",
    "ModelRouter",
)


def _class_owners(class_name: str) -> list[str]:
    pattern = re.compile(rf"^class\s+{re.escape(class_name)}\b", re.MULTILINE)
    owners: list[str] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".git/", ".venv/", "venv/")):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(text):
            owners.append(rel)
    return sorted(owners)


def test_phase11_model_runtime_has_single_semantic_owner() -> None:
    for class_name in OWNED_CLASSES:
        assert _class_owners(class_name) == [CANONICAL_OWNER], (
            f"{class_name} must have exactly one canonical owner; "
            f"found {_class_owners(class_name)}"
        )


def test_capacity_router_is_not_a_second_model_router() -> None:
    capacity_router = (
        ROOT / "execution" / "inference_capacity_router.py"
    ).read_text(encoding="utf-8")
    assert "class InferenceCapacityRouter" in capacity_router
    assert "class ModelRouter" not in capacity_router
    assert "ModelCapabilityRegistry" not in capacity_router
