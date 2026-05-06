from __future__ import annotations

from core.pricing.stop_loss import StopLossDecision, StopLossPolicy, StopLossWindow
from interfaces.web.common.http_response import HttpResponse
from interfaces.web.debug.common.html_escape import esc
from interfaces.web.settings.common.form_bool import parse_bool
from interfaces.web.settings.common.page_query import PageQuery
from interfaces.web.settings.common.save_command import SaveCommand
from runtime.platform.event_store._declared_absence_guard import CANON_DECLARED_ABSENCE, exported_names


def test_shared_web_common_surfaces_are_import_stable() -> None:
    response = HttpResponse(status_code=200, content_type="text/plain", body="ok")
    assert response.status_code == 200
    assert esc('<x>') == '&lt;x&gt;'
    assert parse_bool('YES') is True
    assert PageQuery(tenant_id='t').tenant_id == 't'
    assert SaveCommand(tenant_id='t', payload={'ok': True}).payload['ok'] is True


def test_placeholder_guard_exports_explicit_non_runtime_marker() -> None:
    assert CANON_DECLARED_ABSENCE is True
    assert exported_names('A', '', 'B') == ['CANON_DECLARED_ABSENCE', 'build_declared_absence_metadata', 'declared_absence_runtime_error', 'A', 'B']


def test_stop_loss_surface_is_centralized() -> None:
    assert StopLossDecision.__name__ == "StopLossDecision"
    assert StopLossPolicy.__name__ == "StopLossPolicy"
    assert StopLossWindow.__name__ == "StopLossWindow"
