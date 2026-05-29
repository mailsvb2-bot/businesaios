from datetime import UTC, datetime

from core.contracts.revenue_sprint import RevenueSprintConfig
from core.ux.boost_controller import BoostController


class MemKV:
    def __init__(self):
        self.d = {}

    def get_json(self, key, default):
        return self.d.get(key, default)

    def set_json(self, key, value):
        self.d[key] = value


def test_boost_starts_sprint():
    kv = MemKV()
    bc = BoostController(kv=kv, config=RevenueSprintConfig())
    now = datetime(2026, 3, 1, tzinfo=UTC)
    res = bc.start_or_status(tenant_id="t1", now_utc=now)
    assert res.started is True
    res2 = bc.start_or_status(tenant_id="t1", now_utc=now)
    assert res2.started is False
