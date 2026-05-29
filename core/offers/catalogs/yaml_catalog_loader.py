from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from config.env_flags import env_bool
from config.yaml_loader_shared import load_yaml
from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1
from core.offers.catalogs.yaml_schema import validate_yaml_offer_catalog_spec


def _resolved_catalog_path(*, base_dir: Path, filename: str) -> Path:
    base = Path(base_dir).resolve()
    path = (base / str(filename)).resolve()
    if base not in path.parents and path != base:
        raise ValueError("OFFERS_PATH_OUTSIDE_BASE")
    return path


def load_yaml_offer_catalog_spec(*, base_dir: Path, filename: str, strict: bool | None = None) -> dict[str, Any]:
    path = _resolved_catalog_path(base_dir=base_dir, filename=filename)
    raw = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("BAD_OFFER_CATALOG")
    strict_mode = False if strict is None else bool(strict)
    if strict_mode:
        validate_yaml_offer_catalog_spec(raw)
    return dict(raw)


def load_all_yaml_offer_catalog_specs(*, base_dir: Path, strict: bool | None = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    base = Path(base_dir)
    strict_mode = False if strict is None else bool(strict)
    if not base.exists() or not base.is_dir():
        return out
    for file in sorted(base.glob("*.yaml")):
        try:
            spec = load_yaml_offer_catalog_spec(base_dir=base, filename=file.name, strict=strict_mode)
            catalog_id = str(spec.get("catalog_id") or "").strip()
            if catalog_id:
                out[catalog_id] = spec
        except Exception:
            if strict_mode:
                raise
            continue
    return out


@dataclass(frozen=True)
class YamlOfferCatalogLoaderV1:
    """Loads YAML catalogs from a directory (engine-level).

    Security: blocks path traversal by resolving within base_dir.
    """

    base_dir: Path

    def load_file(self, filename: str) -> YamlOfferCatalogV1:
        strict_mode = env_bool("OFFER_CATALOGS_STRICT", False) or env_bool("CI", False)
        spec = load_yaml_offer_catalog_spec(base_dir=self.base_dir, filename=filename, strict=strict_mode)
        return YamlOfferCatalogV1.from_spec(spec)

    def load_all(self) -> dict[str, YamlOfferCatalogV1]:
        strict_mode = env_bool("OFFER_CATALOGS_STRICT", False) or env_bool("CI", False)
        specs = load_all_yaml_offer_catalog_specs(base_dir=self.base_dir, strict=strict_mode)
        return {catalog_id: YamlOfferCatalogV1.from_spec(spec) for catalog_id, spec in specs.items()}
