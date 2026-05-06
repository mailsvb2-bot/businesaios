"""Behavioral operator catalogs.

Analog to offer catalogs, but for Behavioral OS operators.

Catalogs tune coefficients (phase gain, ring couplings, anti drain,
per-event multipliers) while the operator alphabet remains fixed in code.
"""

from .default_registry import default_operator_catalog_registry
from .models import OperatorCatalog, catalog_from_raw
from .operator_catalog_resolver import OperatorCatalogKey, OperatorCatalogResolver
from .registry import OperatorCatalogRegistry
from .resolver import resolve_operator_catalog_id, resolve_operator_context

__all__ = [
    "OperatorCatalog",
    "catalog_from_raw",
    "OperatorCatalogRegistry",
    "default_operator_catalog_registry",
    "OperatorCatalogKey",
    "OperatorCatalogResolver",
    "resolve_operator_catalog_id",
    "resolve_operator_context",
]
