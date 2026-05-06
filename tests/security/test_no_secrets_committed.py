import re
from pathlib import Path


PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ya\.[A-Za-z0-9_\-]{20,}"),
]


def test_no_secrets_in_repo():
    root = Path(__file__).resolve().parents[2]
    bad = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".zip", ".pdf"}:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for pat in PATTERNS:
            if pat.search(txt):
                bad.append(str(p.relative_to(root)))
                break
    assert not bad, f"Possible secrets detected in: {bad}"
