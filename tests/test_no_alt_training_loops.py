import pathlib
import re


# Guardrail: forbid alternative training loops in-repo.
# IMPORTANT: use word-boundary regex to avoid false positives like "unit_profit(".
FORBIDDEN_CALL_PATTERNS = [
    r"\bretrain\s*\(",
    r"\bfit\s*\(",
    r"\bpartial_fit\s*\(",
]

_FORBIDDEN_RE = re.compile("|".join(FORBIDDEN_CALL_PATTERNS))


def test_no_alt_training_loops():
    repo = pathlib.Path(__file__).resolve().parents[1]

    for py in repo.rglob("*.py"):
        rel = py.relative_to(repo).as_posix()
        if rel.startswith("runtime/platform/support/"):
            continue
        # Allow demos/examples to contain training loop keywords.
        if "examples" in py.parts:
            continue
        text = py.read_text(encoding="utf-8")

        if "PolicyLoop" in text:
            continue

        m = _FORBIDDEN_RE.search(text)
        assert m is None, f"Forbidden training path in {py}: matched {m.group(0)!r}"
