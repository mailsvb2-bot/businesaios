from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_SNIPPETS = (
    "next((",
    "default_action",
    "final_action",
    "resolved_action",
    "recommended_action",
)

ALLOWED_PATH_FRAGMENTS = (
    "tests/",
    "core/ai/decision_core.py",
    "docs/",
)

def test_no_hidden_narrowing_patterns_in_sensitive_areas() -> None:
    offenders: list[str] = []

    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if any(fragment in rel for fragment in ALLOWED_PATH_FRAGMENTS):
            continue

        if not (
            rel.startswith("core/growth/")
            or rel.startswith("core/reward/")
            or rel.startswith("core/economics/")
            or rel.startswith("core/ml/")
            or rel.startswith("ml/")
            or rel.startswith("runtime/")
        ):
            continue

        text = p.read_text(encoding="utf-8", errors="ignore")
        for snippet in FORBIDDEN_SNIPPETS:
            if snippet in text:
                offenders.append(f"{rel}:{snippet}")

    assert not offenders, f"forbidden narrowing patterns found: {offenders}"
