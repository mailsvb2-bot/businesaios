from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True


from typing import Any, Dict


from runtime.boot.env import env_bool

from bootstrap.world_model_builder import build_default_world_model, describe_default_world_model


class WorldModelBootIntegrityError(RuntimeError):
    pass


def verify_boot_world_model_integrity(*, world_model: Any) -> Dict[str, Any]:
    """
    Проверяет, что в boot реально установлен канонический world model path.
    """
    enrich = getattr(world_model, "enrich_state", None)
    if not callable(enrich):
        raise WorldModelBootIntegrityError("boot world_model does not implement enrich_state")

    impl = f"{world_model.__class__.__module__}.{world_model.__class__.__name__}"
    builder_info = describe_default_world_model()

    if impl != builder_info["implementation"]:
        raise WorldModelBootIntegrityError(
            f"unexpected world_model implementation: {impl} != {builder_info['implementation']}"
        )

    return {
        "ok": True,
        "implementation": impl,
        "builder": builder_info["builder"],
        "kind": builder_info["kind"],
    }


def build_and_verify_default_world_model(*, event_log: Any | None = None, store: Any | None = None) -> Any:
    """Build the canonical world model for boot.

    event_log is accepted for backward-compatible boot wiring only; the
    canonical builder currently does not require it. Keeping the parameter on
    the boundary prevents boot-path drift without introducing a second world
    model implementation.
    """
    _ = event_log
    world_model = build_default_world_model(store=store)
    verify_boot_world_model_integrity(world_model=world_model)
    return world_model


def is_world_model_integrity_strict() -> bool:
    return env_bool("STRICT_WORLD_MODEL_BOOT_INTEGRITY", True)
