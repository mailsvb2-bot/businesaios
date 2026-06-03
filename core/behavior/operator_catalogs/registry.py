from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from collections.abc import Mapping

from core.behavior.operator_catalogs.models import OperatorCatalog, catalog_from_raw
from core.behavior.operator_catalogs.yaml_loader import YamlOperatorCatalogLoader


@dataclass
class OperatorCatalogRegistry:
    """In-process registry for operator catalogs."""

    base_dir: Path
    _catalogs: dict[str, OperatorCatalog] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._catalogs = {}
        self.reload()

    def reload(self) -> None:
        loader = YamlOperatorCatalogLoader(base_dir=self.base_dir)
        raws = loader.load_all_raw()
        cats: dict[str, OperatorCatalog] = {}
        for cid, raw in raws.items():
            try:
                cats[cid] = catalog_from_raw(raw)
            except Exception:
                # best-effort: skip invalid catalogs
                continue
        self._catalogs = cats

    def get(self, catalog_id: str) -> OperatorCatalog | None:
        return self._catalogs.get(str(catalog_id or "").strip())

    def as_dict(self) -> dict[str, Mapping[str, Any]]:
        return {cid: {
            "catalog_id": c.catalog_id,
            "phase_gain": float(c.phase_gain),
            "k_tp": float(c.k_tp),
            "k_vp": float(c.k_vp),
            "k_it": float(c.k_it),
            "anti_drain": float(c.anti_drain),
            "event_scales": dict(c.event_scales or {}),
            "domain_scales": dict(c.domain_scales or {}),
        } for cid, c in dict(self._catalogs or {}).items()}
