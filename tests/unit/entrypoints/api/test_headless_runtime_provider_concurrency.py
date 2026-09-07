from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace

import entrypoints.api.headless_runtime_provider as provider_module


def test_headless_runtime_provider_builds_one_runtime_under_concurrency(monkeypatch) -> None:
    workers = 12
    start = Barrier(workers)
    call_lock = Lock()
    runtime = SimpleNamespace(contract=object(), business_memory_query=object())
    calls = 0

    def build_runtime():
        nonlocal calls
        with call_lock:
            calls += 1
        time.sleep(0.05)
        return runtime

    monkeypatch.setattr(provider_module, "build_headless_runtime", build_runtime)
    provider = provider_module.build_default_headless_runtime_provider()

    def acquire_runtime():
        start.wait(timeout=5)
        return provider.get_runtime()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda _: acquire_runtime(), range(workers)))

    assert calls == 1
    assert all(result is runtime for result in results)
    assert provider.business_memory_query() is runtime.business_memory_query
