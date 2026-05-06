from application.business_autonomy.adapters.shopify_production_adapter import ShopifyCredentials, ShopifyProductionAdapter
from application.business_autonomy.adapters.telegram_production_adapter import TelegramBotCredentials, TelegramProductionAdapter
from observability.export_pipeline.clickhouse_exporter import ClickHouseExporter, ClickHouseExporterConfig
from reliability.redis_idempotency_backend import RedisIdempotencyBackend, RedisIdempotencyConfig
from runtime.backends.postgres_backend import ProductionPostgresBackend, ProductionPostgresBackendConfig


class FakeRedis:
    def __init__(self) -> None:
        self.store = {}
        self.counters = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def ttl(self, key):
        return 60

    def delete(self, key):
        self.store.pop(key, None)
        return 1

    def eval(self, script, numkeys, *keys_and_args):
        key = keys_and_args[0]
        expected_version = int(keys_and_args[1])
        body = keys_and_args[2]
        current = self.store.get(key)
        if current is None:
            return 0
        import json
        decoded = json.loads(current)
        if int(decoded.get('version') or 0) != expected_version:
            return 0
        self.store[key] = body
        return 1


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.commands = []
        self.inserts = []

    def command(self, sql, *args, **kwargs):
        self.commands.append(sql)
        return 1

    def insert(self, table, data, column_names):
        self.inserts.append((table, data, column_names))
        return {'ok': True}


def test_production_backends_and_adapters_support_dry_run_contracts() -> None:
    pg = ProductionPostgresBackend(ProductionPostgresBackendConfig(dsn='postgres://user:pass@host/db'))
    assert pg.healthcheck(dry_run=True)['status'] == 'ready_for_credentials'

    redis_backend = RedisIdempotencyBackend(client=FakeRedis(), config=RedisIdempotencyConfig(redis_url='redis://localhost:6379'))
    assert redis_backend.healthcheck(dry_run=True)['status'] == 'ready_for_credentials'
    store = redis_backend.build_store()
    assert store is not None

    exporter = ClickHouseExporter(client=FakeClickHouseClient(), config=ClickHouseExporterConfig(endpoint='https://clickhouse.example.com', database='analytics'))
    assert exporter.healthcheck(dry_run=True)['status'] == 'ready_for_credentials'
    assert exporter.export_events(rows=[{'event': 'x', 'tenant_id': 'tenant-demo'}], dry_run=True)['status'] == 'prepared'

    TelegramBotCredentials(bot_token='123:abc').validate()
    ShopifyCredentials(shop_domain='demo.myshopify.com', admin_access_token='token').validate()
    assert TelegramProductionAdapter().adapter_key == 'chatbot.telegram'
    assert ShopifyProductionAdapter().adapter_key == 'commerce.shopify'
