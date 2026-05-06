from __future__ import annotations

import runtime.bootstrap as runtime_bootstrap


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def build_crm_service(self):
        self.calls.append(("build_crm_service", None))
        return "crm-service"


def test_runtime_bootstrap_package_loads_crm_service_lazily(monkeypatch) -> None:
    recorder = _Recorder()

    monkeypatch.setattr(runtime_bootstrap, "_load_attr", lambda module_name, attr_name: recorder.build_crm_service)

    result = runtime_bootstrap.build_crm_service()

    assert result == "crm-service"
    assert recorder.calls == [("build_crm_service", None)]
