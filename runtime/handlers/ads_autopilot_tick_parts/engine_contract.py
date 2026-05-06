from __future__ import annotations

from runtime.ads import AdsAutopilotRequest


class AdsAutopilotTickContractViolation(RuntimeError):
    pass


def assert_tick_engine(engine) -> None:
    if engine is None:
        raise AdsAutopilotTickContractViolation("engine_missing")
    tick = getattr(engine, "tick", None)
    if not callable(tick):
        raise AdsAutopilotTickContractViolation("engine_tick_missing")


def assert_request_safe(req: AdsAutopilotRequest) -> None:
    req.validate()
    req.validate_executor_route()
    if req.allow_apply():
        raise AdsAutopilotTickContractViolation("direct_apply_forbidden")
