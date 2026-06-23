from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from runtime.platform.economics.world_model_store_contracts import WorldModelStorePort
from storage.postgres_session import PostgresSessionFactory

logger = logging.getLogger(__name__)

CANON_POSTGRES_WORLD_MODEL_STORE = (
    "postgres-backed world model store; no file fallback once selected"
)


@dataclass(frozen=True)
class PostgresWorldModelStore(WorldModelStorePort):
    """Postgres implementation of WorldModelStorePort.

    Contract:
    - platform layer returns JSON-like dict payloads only;
    - no core imports;
    - tenant/product scope is explicit;
    - active model selection is stored in Postgres;
    - schema is small and idempotently ensured on construction.
    """

    dsn: str
    application_name: str = "businesaios-world-model-store"

    def __post_init__(self) -> None:
        if not str(self.dsn).strip():
            raise ValueError("PostgresWorldModelStore requires non-empty dsn")
        self._ensure_schema()

    @property
    def _sessions(self) -> PostgresSessionFactory:
        return PostgresSessionFactory(
            self.dsn,
            application_name=self.application_name,
        )

    def _ensure_schema(self) -> None:
        with self._sessions.open() as session:
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS world_model_payloads (
                    tenant_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (tenant_id, product_id, model_id)
                );
                """
            )
            session.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_world_model_active
                    ON world_model_payloads (tenant_id, product_id)
                    WHERE is_active;
                """
            )
            session.commit()

    def get_active_payload(self, *, tenant_id: str, product_id: str) -> dict[str, Any] | None:
        tenant = str(tenant_id).strip()
        product = str(product_id).strip()
        if not tenant or not product:
            return None

        with self._sessions.open() as session:
            row = session.fetchone(
                """
                SELECT payload
                FROM world_model_payloads
                WHERE tenant_id = %s
                  AND product_id = %s
                  AND is_active = TRUE
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1;
                """,
                (tenant, product),
            )

        if row is None:
            return None

        payload = row.get("payload")
        if payload is None:
            return None

        if isinstance(payload, dict):
            return dict(payload)

        if isinstance(payload, str):
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning(
                    "world_model_store: invalid postgres JSON payload tenant=%s product=%s",
                    tenant,
                    product,
                )
                return None
            return decoded if isinstance(decoded, dict) else None

        logger.warning(
            "world_model_store: unsupported postgres payload type tenant=%s product=%s type=%s",
            tenant,
            product,
            type(payload).__name__,
        )
        return None


__all__ = [
    "CANON_POSTGRES_WORLD_MODEL_STORE",
    "PostgresWorldModelStore",
]
