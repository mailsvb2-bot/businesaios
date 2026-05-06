from __future__ import annotations

"""Engine Marketplace (optional).

This module allows treating product definitions as packages:
  - products/*.yaml as configs
  - python modules as plugins
  - manifest constraints / version pins

The current implementation stays intentionally small:
  - list available product configs
  - read typed manifest if present
  - build a stable package index for platform onboarding
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from runtime.platform.config.registry import CONFIG


@dataclass(frozen=True)
class ProductPackage:
    config_file: str
    product_id: str
    domain: str
    version: str


@dataclass(frozen=True)
class MarketplaceManifest:
    schema_version: int = 1
    registry_id: str = "default"
    title: str = "BusinesAIOS Product Registry"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "registry_id": str(self.registry_id),
            "title": str(self.title),
        }


def list_product_configs(base_dir: Path) -> List[str]:
    return sorted([p.name for p in base_dir.glob("*.yaml") if p.is_file()])


def read_manifest(base_dir: Path) -> Dict[str, Any]:
    path = base_dir / "manifest.yaml"
    if not path.exists():
        return MarketplaceManifest().to_dict()
    raw = CONFIG.yaml_from_path(path)
    if not isinstance(raw, dict):
        return MarketplaceManifest().to_dict()
    manifest = MarketplaceManifest(
        schema_version=int(raw.get("schema_version") or 1),
        registry_id=str(raw.get("registry_id") or "default"),
        title=str(raw.get("title") or "BusinesAIOS Product Registry"),
    )
    out = manifest.to_dict()
    for key, value in raw.items():
        if key not in out:
            out[str(key)] = value
    return out


def index_packages(base_dir: Path) -> List[ProductPackage]:
    out: List[ProductPackage] = []
    for name in list_product_configs(base_dir):
        raw = CONFIG.yaml_from_path(base_dir / name)
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("product_id") or "").strip()
        dom = str(raw.get("domain") or "").strip()
        ver = str(raw.get("product_version") or raw.get("version") or "v1").strip()
        if pid and dom:
            out.append(ProductPackage(config_file=name, product_id=pid, domain=dom, version=ver))
    return out
