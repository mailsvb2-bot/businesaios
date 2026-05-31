from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class WorldModelDefaults:
    unknown_stage: str = "unknown"
    unknown_segment: str = "unknown"
    unknown_title: str = "unknown"
    unknown_inventory_status: str = "unknown"
    unknown_demand_level: str = "unknown"
    unknown_demand_trend: str = "unknown"
    unknown_seasonality: str = "unknown"
    world_snapshot_schema_version: str = "world_snapshot@v1"
    lesson_query_limit: int = 20
    memory_retrieval_max_items: int = 10
    memory_relevance_floor: float = 0.45
    memory_freshness_floor: float = 0.35
    memory_min_support_count: int = 1
    sessions_default: int = 0
    purchases_default: int = 0
    demand_confidence_default: float = 0.0
    demand_revenue_7d_default: float = 0.0
    demand_orders_7d_default: int = 0
    world_snapshot_built_at_default: int = 0


DEFAULT_WORLD_MODEL_DEFAULTS = WorldModelDefaults()


__all__ = ["WorldModelDefaults", "DEFAULT_WORLD_MODEL_DEFAULTS"]
