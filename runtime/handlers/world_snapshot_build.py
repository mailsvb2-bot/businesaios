from __future__ import annotations

CANON_THIN_HANDLER = True

from runtime.world_model import WorldModelBuildInput, WorldModelBuildResult, WorldModelService


def handle_world_snapshot_build(service: WorldModelService, build_input: WorldModelBuildInput) -> WorldModelBuildResult:
    return service.build_snapshot(build_input=build_input)
