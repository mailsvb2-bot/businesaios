from __future__ import annotations

import boot.bootstrap as legacy_bootstrap
import runtime.bootstrap as runtime_bootstrap


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def process_bootstrap(self, *, acquire_singleton_lock: bool = True) -> None:
        self.calls.append(("process", acquire_singleton_lock))


def test_runtime_bootstrap_root_delegates_to_internal_process_owner(monkeypatch) -> None:
    recorder = _Recorder()

    monkeypatch.setattr(runtime_bootstrap, "_load_process_bootstrap_owner", lambda: recorder.process_bootstrap)

    runtime_bootstrap.bootstrap(acquire_singleton_lock=False)

    assert recorder.calls == [("process", False)]


def test_legacy_bootstrap_delegates_to_bootstrap_compose_owner(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    class _Runtime:
        ready = True

    def _load_attr(module_name: str, attr_name: str):
        mapping = {
            ("bootstrap.compose", "bootstrap"): lambda *, acquire_singleton_lock=True: calls.append(("compose.bootstrap", acquire_singleton_lock)),
            ("bootstrap.compose", "get_bootstrapped_runtime"): lambda: calls.append(("compose.get_runtime", None)) or _Runtime(),
        }
        return mapping[(module_name, attr_name)]

    monkeypatch.setattr(legacy_bootstrap, "_load_attr", _load_attr)

    runtime = legacy_bootstrap.bootstrap(acquire_singleton_lock=False)

    assert runtime.ready is True
    assert calls == [
        ("compose.bootstrap", False),
        ("compose.get_runtime", None),
    ]
