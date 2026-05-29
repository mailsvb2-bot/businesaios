from __future__ import annotations

"""Validate offer catalogs in data/offer_catalogs.

Why a script (not only tests):
- CI can run it independently (fast, no imports from runtime)
- Useful locally before pushing a patchset of YAML catalogs

This script is intentionally conservative: it checks the minimal structural
requirements (catalog_id optional, offers list required, each offer has id).
"""

import sys
from pathlib import Path
from typing import Any

from runtime.platform.config.yaml_loader import load_yaml


def _err(code: str, path: Path, msg: str) -> tuple[str, str, str]:
    return (code, str(path), msg)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        return load_yaml(path)
    except ValueError:
        raise ValueError("CATALOG_NOT_MAPPING")


def _validate_catalog(doc: dict[str, Any]) -> None:
    if "catalog_id" in doc:
        if not isinstance(doc.get("catalog_id"), str) or not doc["catalog_id"].strip():
            raise ValueError("BAD_catalog_id")

    if "offers" not in doc:
        raise ValueError("MISSING_offers")
    if not isinstance(doc["offers"], list):
        raise ValueError("BAD_offers_type")

    for i, o in enumerate(doc["offers"]):
        if not isinstance(o, dict):
            raise ValueError(f"BAD_offer_{i}")
        oid = o.get("offer_id") or o.get("id")
        if not isinstance(oid, str) or not oid.strip():
            raise ValueError(f"MISSING_offer_id_{i}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    base = Path("data") / "offer_catalogs"
    if len(sys.argv) >= 2:
        base = Path(sys.argv[1])

    base = base.resolve()
    if not base.exists():
        print(f"[offers-validate] OK (no dir): {base}")
        return 0

    errors: list[tuple[str, str, str]] = []
    files = sorted(list(base.rglob("*.yaml")) + list(base.rglob("*.yml")))
    for p in files:
        try:
            doc = _load_yaml(p)
            _validate_catalog(doc)
        except Exception as e:
            errors.append(_err("INVALID_CATALOG", p, str(e)))

    if errors:
        for code, path, msg in errors:
            print(f"[offers-validate] {code} :: {path} :: {msg}")
        return 2

    print(f"[offers-validate] OK :: scanned={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
