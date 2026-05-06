from __future__ import annotations

BOUNDARIES = {
    "training": {"can_publish": False, "can_promote": False, "can_mutate_objective": False},
    "serving": {"can_publish": False, "can_promote": False, "can_mutate_objective": False},
    "evaluation": {"can_recommend": True, "can_publish": False, "can_promote": False},
    "rollout": {"can_collect": True, "can_publish": False, "can_promote": False},
    "safety": {"can_block": True, "can_publish": False, "can_promote": False},
}


def boundary_allows(module_name: str, capability: str) -> bool:
    return bool(BOUNDARIES.get(module_name, {}).get(capability, False))

__all__ = [
    "BOUNDARIES",
    "boundary_allows",
]
