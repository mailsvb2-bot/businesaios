from __future__ import annotations

from pathlib import Path


def persist_pricing_version_override(*, override_path: Path, pricing_version: str) -> bool:
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(str(pricing_version) + "\n", encoding="utf-8")
    return True
