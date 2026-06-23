from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CANON_WORLD_MODEL_STORE_CONTRACTS = True


class WorldModelStorePort:
    """Contract for governed world-model payload loading."""

    def get_active_payload(self, *, tenant_id: str, product_id: str) -> dict[str, Any] | None:
        ...


@dataclass(frozen=True)
class FileWorldModelStore(WorldModelStorePort):
    base_dir: Path

    def _path(self, tenant_id: str, product_id: str) -> Path:
        return Path(self.base_dir) / str(tenant_id) / str(product_id)

    def get_active_payload(self, *, tenant_id: str, product_id: str) -> dict[str, Any] | None:
        root = self._path(tenant_id, product_id)
        active = root / "ACTIVE"
        if not active.exists():
            return None
        model_id = active.read_text(encoding="utf-8").strip()
        if not model_id:
            return None
        path = root / f"{model_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.warning("world_model_store: failed to load %s: %s", path, exc)
            return None


__all__ = [
    "CANON_WORLD_MODEL_STORE_CONTRACTS",
    "FileWorldModelStore",
    "WorldModelStorePort",
]
