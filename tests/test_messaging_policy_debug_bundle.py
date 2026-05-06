from interfaces.web.debug.messaging_policy_snapshot.route_bundle import MessagingPolicySnapshotRouteBundle
from runtime.boot.web.runtime_web_bundle import RuntimeWebBundle
from runtime.boot.web.runtime_web_services import RuntimeWebServices


class _ReadService:
    def __init__(self, value):
        self._value = value

    def get_snapshot(self, *, tenant_id: str, user_id: str, correlation_id: str):
        return self._value


class _App:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def deco(fn):
            self.routes[path] = fn
            return fn
        return deco


def test_bundle_serves_json_and_html():
    bundle = MessagingPolicySnapshotRouteBundle(read_service=_ReadService({'tenant_id': 't1', 'user_id': 'u1', 'correlation_id': 'c1', 'delivered': ['sms'], 'failed': ['telegram'], 'blocked': [], 'last_plan_channels': ['telegram', 'sms'], 'last_selected_channel': 'sms', 'last_terminal_reason': '', 'attempts_count': 2}))
    j = bundle.json(tenant_id='t1', user_id='u1', correlation_id='c1')
    h = bundle.html(tenant_id='t1', user_id='u1', correlation_id='c1')
    assert j.status_code == 200
    assert j.body['last_selected_channel'] == 'sms'
    assert h.status_code == 200
    assert 'Messaging Policy Snapshot' in h.body


def test_runtime_web_bundle_registers_debug_routes_when_services_present():
    app = _App()
    bundle = RuntimeWebBundle(services=RuntimeWebServices(project_root='.', settings_gateway=None, messaging_policy_read_service=_ReadService(None), messaging_policy_event_store=object()))
    bundle.boot_fastapi(app=app)
    assert '/api/debug/messaging-policy-snapshot' in app.routes
    assert '/api/debug/messaging-policy-traces' in app.routes
    assert '/api/debug/messaging-policy-alerts' in app.routes
