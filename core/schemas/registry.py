from __future__ import annotations

from typing import Dict, Tuple

from .base import Schema, SchemaId


class SchemaRegistry:
    """
    Единственный реестр схем системы.
    """

    def __init__(self) -> None:
        self._schemas: Dict[Tuple[str, int], Schema] = {}

    # --------------------------
    # Registration
    # --------------------------

    def register(self, schema_id: SchemaId, schema: Schema) -> None:
        key = (schema_id.name, schema_id.version)

        if key in self._schemas:
            raise RuntimeError(f"Schema already registered: {key}")

        self._schemas[key] = schema

    # --------------------------
    # Lookup
    # --------------------------

    def get(self, schema_id: SchemaId) -> Schema:
        key = (schema_id.name, schema_id.version)

        if key not in self._schemas:
            raise RuntimeError(f"Unknown schema: {key}")

        return self._schemas[key]

    # --------------------------
    # Validation
    # --------------------------

    def validate(self, schema_id: SchemaId, payload: dict) -> None:
        schema = self.get(schema_id)
        schema.validate(payload)

    # --------------------------
    # Canonical decoding
    # --------------------------

    def normalize(self, schema_id: SchemaId, payload: dict) -> dict:
        schema = self.get(schema_id)
        return schema.normalize(payload)
