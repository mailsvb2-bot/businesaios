from __future__ import annotations

from runtime.boot.web.messaging_policy_dashboard_boot import boot_messaging_policy_dashboard


class _Graph:
    trace_search_service = object()


class _Bundle:
    pass


def test_dashboard_boot_has_single_bundle_owner(monkeypatch) -> None:
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        'runtime.boot.web.messaging_policy_dashboard_boot.build_messaging_policy_service_graph',
        lambda *, event_store: _Graph(),
    )
    monkeypatch.setattr(
        'runtime.boot.web.messaging_policy_dashboard_boot.build_messaging_policy_dashboard_bundle',
        lambda *, trace_search_service: _Bundle(),
    )

    def _registrar(*, app, bundle) -> None:
        calls.append((app, bundle))

    app = object()
    boot_messaging_policy_dashboard(app=app, event_store=object(), route_registrar=_registrar)
    assert calls and calls[0][0] is app
    assert isinstance(calls[0][1], _Bundle)
