from __future__ import annotations

from pathlib import Path
from typing import List

from .constants import BOOT_WIRING_LINE_LIMIT
from .domain_discovery import line_count, read_text_safe, rel
from .findings import CanonFsFinding

SIZE_LIMIT_EXEMPT_BOOT_FILES: tuple[str, ...] = (
    "runtime/boot/boot_context.py",
    "runtime/boot/boot_core_assembly.py",
    "runtime/boot/product_system_builder.py",
)


FORBIDDEN_BOOT_TOKENS: tuple[str, ...] = (
    "requests.",
    "httpx.",
    "asyncio.create_task(",
    "subprocess.",
    "Popen(",
    "def decide(",
    "def choose_strategy(",
    "apply_campaign(",
    "execute_action(",
)


def scan_boot_wiring_only(root: Path) -> List[CanonFsFinding]:
    boot = root / "runtime" / "boot"
    findings: List[CanonFsFinding] = []

    if not boot.exists():
        return findings

    for path in boot.rglob("*.py"):
        text = read_text_safe(path)
        if "CANON_BOOT_WIRING_ONLY = True" not in text:
            continue

        rel_path = rel(root, path)

        if rel_path not in SIZE_LIMIT_EXEMPT_BOOT_FILES and line_count(path) > BOOT_WIRING_LINE_LIMIT:
            findings.append(
                CanonFsFinding(
                    path=rel_path,
                    kind="boot-module-too-large",
                    message=f"Boot wiring module exceeds line limit {BOOT_WIRING_LINE_LIMIT}.",
                )
            )

        for token in FORBIDDEN_BOOT_TOKENS:
            if token in text:
                findings.append(
                    CanonFsFinding(
                        path=rel_path,
                        kind="boot-not-wiring-only",
                        message=f"Boot module marked wiring-only contains forbidden token: {token}",
                    )
                )

    return findings