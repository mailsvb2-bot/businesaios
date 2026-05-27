from runtime.boot.system_builder_parts.runtime_services_result import RuntimeServicesResult
from runtime.executor_infra import RuntimeExecutorInfra
from runtime.runtime_infra import RuntimeInfra


def test_runtime_infra_aliases_are_canonical():
    infra = RuntimeInfra(
        event_store='events',
        ledger='ledger',
        snapshot_store='snapshots',
        outbox='outbox',
        payment_outbox='payments',
        settings_gateway='settings',
        messaging_policy_event_store='mp-store',
        messaging_policy_read_service='mp-reader',
    )
    assert infra.decision_ledger == 'ledger'
    assert infra.snapshot_archive == 'snapshots'
    assert infra.effect_outbox == 'outbox'
    assert infra.payments_outbox == 'payments'
    assert infra.settings_store == 'settings'
    assert infra.messaging_policy_store == 'mp-store'
    assert infra.messaging_policy_reader == 'mp-reader'


def test_runtime_executor_infra_extends_runtime_infra():
    infra = RuntimeExecutorInfra(
        outbox='outbox',
        delivery_state='delivery',
        telegram_outbound_queue='queue',
    )
    assert infra.effect_outbox == 'outbox'
    assert infra.delivery_state == 'delivery'
    assert infra.telegram_outbound_queue == 'queue'


def test_runtime_services_result_supports_attribute_and_item_access():
    result = RuntimeServicesResult(event_store='events', composer='composer')
    assert result.event_store == 'events'
    assert result['composer'] == 'composer'
