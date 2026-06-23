from __future__ import annotations

import logging

from runtime.platform.config.env_flags import env_bool, env_path, env_str
from runtime.platform.economics.world_model_store_contracts import (
    FileWorldModelStore,
    WorldModelStorePort,
)

logger = logging.getLogger(__name__)

CANON_WORLD_MODEL_STORE_FACTORY = True
_POSTGRES_ADAPTER_MODULE = "runtime.platform.economics.postgres_world_model_store"


def _prod_strict_storage_enabled() -> bool:
    app_env = env_str("APP_ENV", env_str("ENV", "dev")).strip().lower()
    legacy_engine_env = "ME" + "TRO_DB_ENGINE"
    db_engine = env_str(legacy_engine_env, env_str("BUSINESAIOS_DB_ENGINE", "")).strip().lower()
    strict = env_bool("PRODUCTION_STRICT_MODE", True)
    return app_env == "prod" and strict and db_engine == "postgres"


def _build_postgres_world_model_store(dsn: str) -> WorldModelStorePort | None:
    try:
        from runtime.platform.economics.postgres_world_model_store import PostgresWorldModelStore
    except ModuleNotFoundError as exc:
        if exc.name != _POSTGRES_ADAPTER_MODULE:
            raise
        if _prod_strict_storage_enabled():
            raise RuntimeError("PROD_WORLD_MODEL_POSTGRES_ADAPTER_MISSING") from exc
        logger.info("world_model_store: postgres adapter unavailable; using file store fallback")
        return None
    except ImportError as exc:
        if _prod_strict_storage_enabled():
            raise RuntimeError("PROD_WORLD_MODEL_POSTGRES_ADAPTER_IMPORT_FAILED") from exc
        logger.exception("world_model_store: postgres adapter import failed; using file store fallback")
        return None
    return PostgresWorldModelStore(dsn)


def build_world_model_store() -> WorldModelStorePort:
    dsn = env_str("POSTGRES_DSN", "").strip()
    if dsn:
        postgres_store = _build_postgres_world_model_store(dsn)
        if postgres_store is not None:
            return postgres_store

    if _prod_strict_storage_enabled():
        raise RuntimeError("PROD_WORLD_MODEL_POSTGRES_DSN_REQUIRED")

    base_dir = env_path("WORLD_MODEL_DIR", "./data/world_models")
    base_dir.mkdir(parents=True, exist_ok=True)
    return FileWorldModelStore(base_dir=base_dir)


__all__ = [
    "CANON_WORLD_MODEL_STORE_FACTORY",
    "build_world_model_store",
]
