from interfaces.web.debug.messaging_policy_snapshot.html_controller import MessagingPolicySnapshotHtmlController
from interfaces.web.debug.messaging_policy_snapshot.json_controller import MessagingPolicySnapshotJsonController


class _API:
    def __init__(self, value):
        self._value = value

    def get_snapshot(self, *, tenant_id: str, user_id: str, correlation_id: str):
        return self._value


def test_json_controller_returns_404_on_missing():
    ctrl = MessagingPolicySnapshotJsonController(api_service=_API(None))
    out = ctrl.get_snapshot(tenant_id='t1', user_id='u1', correlation_id='c1')
    assert out.status_code == 404
    assert out.body['error'] == 'SNAPSHOT_NOT_FOUND'


def test_html_controller_renders_snapshot():
    ctrl = MessagingPolicySnapshotHtmlController(api_service=_API({'last_selected_channel': 'email', 'last_terminal_reason': '', 'attempts_count': 1, 'delivered': ['email'], 'failed': [], 'blocked': [], 'last_plan_channels': ['telegram', 'email']}))
    out = ctrl.get_snapshot_page(tenant_id='t1', user_id='u1', correlation_id='c1')
    assert out.status_code == 200
    assert 'email' in out.body
