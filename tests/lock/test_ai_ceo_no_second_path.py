import pathlib

import pytest


@pytest.mark.lock
def test_ai_ceo_action_single_source_of_truth():
    """Prevent accidental alternative AI CEO entrypoints.

    Allowed occurrences:
    - core/ai_ceo/* (implementation)
    - core/policies/telegram/handlers/ai_ceo.py (routing)
    - runtime/handlers/ai_ceo_plan.py (execution)
    - runtime/boot/actions_catalog.py (canonical action catalog)
    - bootstrap/registration_manifest.py (lock manifest)
    """
    root = pathlib.Path(__file__).resolve().parents[2]
    needle = "ai_ceo_plan@v1"

    allowed = {
        str(root / "core" / "ai_ceo"),
        str(root / "core" / "policies" / "telegram" / "handlers" / "ai_ceo.py"),
        str(root / "runtime" / "handlers" / "ai_ceo_plan.py"),
        str(root / "runtime" / "boot" / "actions_catalog.py"),
        str(root / "runtime" / "boot" / "actions_registry.py"),
        str(root / "runtime" / "boot" / "registration_manifest.py"),
    }

    hits = []
    for p in root.rglob("*.py"):
        if 'tests' in p.parts:
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if needle in txt:
            hits.append(str(p))

    assert hits, "Expected ai_ceo_plan@v1 to be referenced"
    for h in hits:
        ok = False
        for a in allowed:
            if h.startswith(a):
                ok = True
                break
        assert ok, f"Unexpected reference to {needle} in {h} (second path risk)"
