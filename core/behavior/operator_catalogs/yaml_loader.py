from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.yaml_loader_shared import load_yaml


@dataclass(frozen=True)
class YamlOperatorCatalogLoader:
    """Loads operator catalogs from YAML files.

    Files live under products/operator_catalogs/*.yaml.

    This loader is intentionally permissive: unknown keys are ignored,
    and non-dict YAML contents are skipped.
    """

    base_dir: Path

    def load_all_raw(self) -> dict[str, Mapping[str, Any]]:
        out: dict[str, Mapping[str, Any]] = {}
        if not self.base_dir.exists():
            return out
        for p in sorted(self.base_dir.glob("*.yaml")):
            raw = load_yaml(p.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                continue
            cid = str(raw.get("catalog_id") or "").strip()
            if not cid:
                continue
            out[cid] = raw
        return out
