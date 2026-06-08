from __future__ import annotations

from typing import Any


def build_economy(*, enrich: dict[str, Any]) -> dict[str, Any]:
    return {"payments": enrich.get("payments", {}), "entitlements": enrich.get("entitlements", {})}
