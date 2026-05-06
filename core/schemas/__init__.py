from core.schemas.base import SchemaId
from core.schemas.bootstrap import build_schema_registry
from core.schemas.registry import SchemaRegistry

CANON_CORE_SCHEMAS = True

__all__ = [
    "CANON_CORE_SCHEMAS",
    "SchemaId",
    "SchemaRegistry",
    "build_schema_registry",
]
