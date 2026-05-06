from interfaces.web.debug.messaging_policy_snapshot.route_bundle import MessagingPolicySnapshotAPIService


class _ReadService:
    def get_snapshot(self, *, tenant_id: str, user_id: str, correlation_id: str):
        assert tenant_id == 't1'
        assert user_id == 'u1'
        assert correlation_id == 'c1'
        class _Snap:
            tenant_id = 't1'
            user_id = 'u1'
            correlation_id = 'c1'
            delivered = ('sms',)
            failed = ('telegram',)
            blocked = ()
            last_plan_channels = ('telegram', 'sms')
            last_selected_channel = 'sms'
            last_terminal_reason = ''
            attempts_count = 2
        return _Snap()


def test_api_service_reads_snapshot():
    service = MessagingPolicySnapshotAPIService(read_service=_ReadService())
    out = service.get_snapshot(tenant_id='t1', user_id='u1', correlation_id='c1')
    assert out['last_selected_channel'] == 'sms'
    assert out['attempts_count'] == 2
