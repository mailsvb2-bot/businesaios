from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContainerRuntimeProbe:
    image_built: bool
    container_started: bool
    readyz_ok: bool
    storagez_ok: bool
    executionz_ok: bool
    uses_readiness_healthcheck: bool


def evaluate_container_runtime(probe: ContainerRuntimeProbe) -> dict[str, object]:
    violations: list[str] = []
    if not probe.image_built:
        violations.append("container_image_build_required")
    if not probe.container_started:
        violations.append("container_start_required")
    if not probe.readyz_ok:
        violations.append("readyz_required")
    if not probe.storagez_ok:
        violations.append("storagez_required")
    if not probe.executionz_ok:
        violations.append("executionz_required")
    if not probe.uses_readiness_healthcheck:
        violations.append("readiness_healthcheck_required")
    return {
        "artifact": "container_runtime",
        "status": "ready" if not violations else "blocked",
        "image_built": probe.image_built,
        "container_started": probe.container_started,
        "readyz_ok": probe.readyz_ok,
        "storagez_ok": probe.storagez_ok,
        "executionz_ok": probe.executionz_ok,
        "uses_readiness_healthcheck": probe.uses_readiness_healthcheck,
        "violations": violations,
        "claims_production_ready": False,
    }


__all__ = ["ContainerRuntimeProbe", "evaluate_container_runtime"]
