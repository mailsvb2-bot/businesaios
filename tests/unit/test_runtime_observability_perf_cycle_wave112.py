from __future__ import annotations

import importlib


def test_runtime_observability_perf_import_is_cycle_free() -> None:
    perf = importlib.import_module('runtime.observability.perf')
    public_api = importlib.import_module('runtime.observability.public_api')

    assert perf.Span is public_api.Span
    assert perf.emit_sla_violation is public_api.emit_sla_violation
