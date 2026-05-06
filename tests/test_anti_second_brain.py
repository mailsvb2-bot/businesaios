import pathlib
import re


FORBIDDEN = [
    re.compile(r"\bif\s+world_state\b"),
    re.compile(r"\bif\s+state\."),
]


def _scan(root: pathlib.Path):
    for p in root.rglob("*.py"):
        if not p.is_file():
            continue
        yield p, p.read_text(encoding="utf-8", errors="ignore")


def test_no_decision_logic_outside_core():
    # Heuristic barrier: runtime/interfaces should not contain decision branching on world_state/state fields.
    for base in [pathlib.Path("runtime"), pathlib.Path("interfaces")]:
        for p, text in _scan(base):
            for pat in FORBIDDEN:
                assert not pat.search(text), f"possible decision logic outside core in {p}: {pat.pattern}"
