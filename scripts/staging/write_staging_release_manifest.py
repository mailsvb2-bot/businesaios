from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "release" / "manifest.json"


def read_manifest() -> dict[str, object]:
    if not MANIFEST.exists():
        raise FileNotFoundError(
            "release/manifest.json is required for staging container proof; "
            "do not bypass strict bootstrap"
        )
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("release/manifest.json must contain a JSON object")
    payload.setdefault("claims_production_ready", False)
    return payload


def main() -> int:
    read_manifest()
    print(MANIFEST.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
