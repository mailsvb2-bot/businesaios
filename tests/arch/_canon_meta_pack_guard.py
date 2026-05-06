from __future__ import annotations

# CANON_META_PACK: this helper belongs to the canonical meta-pack entry layer.
# CANON_MASTER_LAYER: meta-pack is part of the repository-wide constitutional stack.

from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "docs" / "CANON_META_PACK_MANIFEST_V1.yaml"
INDEX_PATH = ROOT / "docs" / "CANON_META_PACK_INDEX_V1.md"
ONBOARDING_PATH = ROOT / "docs" / "CANON_ONBOARDING_FOR_ARCHITECTS_V1.md"

REQUIRED_PACK_IDS: tuple[str, ...] = (
    "red-flags",
    "decision-space",
    "capabilities",
    "boot-runtime-registry",
    "domain-registry",
    "test-quality",
    "exception-registry",
    "migration-registry",
    "arch-audit",
    "master-layer",
)

@dataclass(frozen=True)
class ManifestPack:
    pack_id: str
    paths: tuple[str, ...]

@dataclass(frozen=True)
class MetaPackManifest:
    meta_pack_id: str
    description: str
    onboarding_doc: str
    index_doc: str
    marker: str
    packs: tuple[ManifestPack, ...]

def _strip_comment(line: str) -> str:
    if "#" in line:
        return line.split("#", 1)[0].rstrip()
    return line.rstrip()

def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and (((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"))):
        return value[1:-1]
    return value

def _parse_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"Invalid manifest line: {text}")
    key, value = text.split(":", 1)
    return key.strip(), _unquote(value.strip())

def load_manifest() -> MetaPackManifest:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(str(MANIFEST_PATH))
    lines = [_strip_comment(line) for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines()]
    marker = ""
    meta_pack_id = ""
    description = ""
    onboarding_doc = ""
    index_doc = ""
    packs: list[dict[str, Any]] = []
    in_meta_pack = False
    in_packs = False
    current_pack: dict[str, Any] | None = None
    current_list_key: str | None = None

    for raw in lines:
        if not raw.strip():
            continue
        stripped = raw.strip()
        if stripped == "meta_pack:":
            in_meta_pack = True
            continue
        if not in_meta_pack:
            continue
        if stripped == "packs:":
            in_packs = True
            continue
        if in_packs and stripped.startswith("- pack_id:"):
            if current_pack is not None:
                packs.append(current_pack)
            current_pack = {}
            current_list_key = None
            key, value = _parse_key_value(stripped[2:].strip())
            current_pack[key] = value
            continue
        if in_packs and current_list_key == "paths" and stripped.startswith("- "):
            if current_pack is None:
                raise ValueError("path item declared before pack")
            current_pack.setdefault("paths", []).append(_unquote(stripped[2:].strip()))
            continue
        if in_packs and stripped == "paths:":
            if current_pack is None:
                raise ValueError("paths declared before pack")
            current_pack["paths"] = []
            current_list_key = "paths"
            continue
        key, value = _parse_key_value(stripped)
        current_list_key = None
        if in_packs:
            if current_pack is None:
                raise ValueError("Pack field declared before pack item")
            current_pack[key] = value
        else:
            if key == "marker":
                marker = value
            elif key == "meta_pack_id":
                meta_pack_id = value
            elif key == "description":
                description = value
            elif key == "onboarding_doc":
                onboarding_doc = value
            elif key == "index_doc":
                index_doc = value

    if current_pack is not None:
        packs.append(current_pack)

    manifest_packs = tuple(
        ManifestPack(pack_id=str(item["pack_id"]), paths=tuple(str(path) for path in item.get("paths", [])))
        for item in packs
    )
    return MetaPackManifest(
        marker=marker,
        meta_pack_id=meta_pack_id,
        description=description,
        onboarding_doc=onboarding_doc,
        index_doc=index_doc,
        packs=manifest_packs,
    )

def all_manifest_paths(manifest: MetaPackManifest) -> list[str]:
    result = [manifest.onboarding_doc, manifest.index_doc]
    for pack in manifest.packs:
        result.extend(pack.paths)
    return sorted(set(result))

def absolute(rel: str) -> Path:
    return ROOT / rel
