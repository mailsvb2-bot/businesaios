from __future__ import annotations

from types import SimpleNamespace

from runtime.experiments.outcome_observer import LiveCanaryOutcomeSupervisor


def test_outcome_supervisor_retries_after_transient_poll_failure() -> None:
    attempts = 0
    circuit_events: list[tuple[str, ...]] = []

    def poll_once() -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("event store temporarily unavailable")
        return 1

    coordinator = SimpleNamespace(
        policy=SimpleNamespace(
            experiment_id="observer-retry",
            allowed_tenant_ids=("tenant-a",),
        ),
        _open_local_circuit=lambda result, **_kwargs: circuit_events.append(
            tuple(result.reasons)
        ),
    )
    observer = SimpleNamespace(poll_once=poll_once, coordinator=coordinator)
    supervisor = LiveCanaryOutcomeSupervisor(observer, interval_seconds=1.0)

    class StopAfterTwoPulses:
        def __init__(self) -> None:
            self.pulses = 0

        def is_set(self) -> bool:
            return self.pulses >= 2

        def wait(self, _seconds: float) -> None:
            self.pulses += 1

    supervisor._stop = StopAfterTwoPulses()
    supervisor._run()

    assert attempts == 2
    assert circuit_events == [("outcome_observer_error:OSError",)]
