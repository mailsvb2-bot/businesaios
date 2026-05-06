import re
from pathlib import Path

from core.actions.allowed_actions import ALLOWED_ACTIONS


def test_policies_do_not_reference_unknown_actions():
    root = Path(__file__).resolve().parents[2]
    policy_dir = root / "core" / "policies"
    if not policy_dir.exists():
        return

    unknown: set[str] = set()
    pat = re.compile(r"[A-Za-z0-9_:\-]+@v\d+")
    for py in policy_dir.rglob("*.py"):
        txt = py.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(txt):
            tok = m.group(0)
            if tok not in ALLOWED_ACTIONS:
                unknown.add(tok)

    assert not unknown, f"Unknown action tokens referenced in policies: {sorted(unknown)}"
