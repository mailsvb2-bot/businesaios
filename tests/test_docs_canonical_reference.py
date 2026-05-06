from pathlib import Path

BAD_PATTERNS = [
    "Единое_супер_ТЗ_системы.txt",
    "docs/Единое_супер_ТЗ_системы.txt",
]

def test_no_obsolete_tz_references():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for p in root.rglob("*.md"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if any(bad in txt for bad in BAD_PATTERNS):
            offenders.append(str(p))
    assert not offenders, "Obsolete TZ references found:\n" + "\n".join(offenders)
