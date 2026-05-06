from __future__ import annotations

from pathlib import Path
from typing import List

from .constants import THIN_HANDLER_LINE_LIMIT
from .domain_discovery import line_count, read_text_safe, rel
from .findings import CanonFsFinding

SIZE_LIMIT_EXEMPT_HANDLERS: tuple[str, ...] = (
    "runtime/handlers/behavior_graph.py",
)


FORBIDDEN_THIN_HANDLER_TOKENS: tuple[str, ...] = (
    "def decide(",
    "def choose_strategy(",
    "def choose_action(",
    "def optimize_strategy(",
    "DecisionRoute(",
    "EXPECTED_ISSUER_ID =",
)


def scan_thin_runtime_handlers(root: Path) -> List[CanonFsFinding]:
    handlers = root / "runtime" / "handlers"
    findings: List[CanonFsFinding] = []

    if not handlers.exists():
        return findings

    for path in handlers.rglob("*.py"):
        text = read_text_safe(path)
        if "CANON_THIN_HANDLER = True" not in text:
            continue

        rel_path = rel(root, path)

        if rel_path not in SIZE_LIMIT_EXEMPT_HANDLERS and line_count(path) > THIN_HANDLER_LINE_LIMIT:
            findings.append(
                CanonFsFinding(
                    path=rel_path,
                    kind="thin-handler-too-large",
                    message=f"Thin runtime handler exceeds line limit {THIN_HANDLER_LINE_LIMIT}.",
                )
            )

        for token in FORBIDDEN_THIN_HANDLER_TOKENS:
            if token in text:
                findings.append(
                    CanonFsFinding(
                        path=rel_path,
                        kind="decision-logic-inside-thin-handler",
                        message=f"Thin runtime handler contains forbidden decision token: {token}",
                    )
                )

    return findings