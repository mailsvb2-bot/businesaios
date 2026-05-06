from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.platform.config.env_flags import env_path, env_str

logger = logging.getLogger(__name__)
_POSTGRES_ADAPTER_MODULE = "runtime.platform.economics.postgres_world_model_store"


class WorldModelStorePort:
    """Platform port: load a governed world-model payload for a tenant/product.

    IMPORTANT (layering):
    - platform_layer MUST NOT import core.
    - Return value is a plain JSON-like dict; conversion to core models happens in runtime.
    """

    def get_active_payload(self, *, tenant_id: str, product_id: str) -> Optional[Dict[str, Any]]: ...


@dataclass(frozen=True)
class FileWorldModelStore(WorldModelStorePort):
    base_dir: Path

    def _path(self, tenant_id: str, product_id: str) -> Path:
        return Path(self.base_dir) / str(tenant_id) / str(product_id)

    def get_active_payload(self, *, tenant_id: str, product_id: str) -> Optional[Dict[str, Any]]:
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
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning("world_model_store: failed to load %s: %s", path, e)
            return None


def _build_postgres_world_model_store(dsn: str) -> WorldModelStorePort | None:
    try:
        from runtime.platform.economics.postgres_world_model_store import PostgresWorldModelStore
    except ModuleNotFoundError as exc:
        if exc.name != _POSTGRES_ADAPTER_MODULE:
            raise
        logger.info("world_model_store: postgres adapter unavailable; using file store fallback")
        return None
    except ImportError:
        logger.exception("world_model_store: postgres adapter import failed; using file store fallback")
        return None
    return PostgresWorldModelStore(dsn)


def build_world_model_store() -> WorldModelStorePort:
    dsn = env_str("POSTGRES_DSN", "").strip()
    if dsn:
        postgres_store = _build_postgres_world_model_store(dsn)
        if postgres_store is not None:
            return postgres_store

    base_dir = env_path("WORLD_MODEL_DIR", "./data/world_models")
    base_dir.mkdir(parents=True, exist_ok=True)
    return FileWorldModelStore(base_dir=base_dir)
