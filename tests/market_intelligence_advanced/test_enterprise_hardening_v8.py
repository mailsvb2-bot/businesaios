from __future__ import annotations

from pathlib import Path

from execution.market_intelligence_business_memory_bridge import MarketIntelligenceBusinessMemoryBridge
from execution.market_intelligence_world_state_adapter import MarketIntelligenceWorldStateAdapter
from kernel.world_state import WorldStateV1
from runtime._internal.market_intelligence.provider_contracts import ProviderContractRegistry
from runtime._internal.market_intelligence.provider_runtime import ProviderRuntimeFactory
from runtime._internal.market_intelligence.recovery import MarketIntelligenceRecoveryController
from runtime._internal.market_intelligence.state_store import SqliteMarketIntelligenceStateStore, SyncCheckpoint


def test_provider_contract_registry_allows_explicit_aliases() -> None:
    registry = ProviderContractRegistry()
    registry.register_alias('meta', 'facebook_ad_library')
    registry.validate_no_hidden_fallback(requested_provider='meta', resolved_provider='facebook_ad_library')


def test_memory_bridge_does_not_fail_when_no_promoted_signals() -> None:
    bridge = MarketIntelligenceBusinessMemoryBridge()
    payload = bridge.to_memory_payload({'provider': 'amazon', 'source_family': 'marketplace', 'records': []})
    assert payload['derived_evidence'] is None
    assert payload['memory_policy_controlled'] is True


def test_world_state_adapter_preserves_existing_fields() -> None:
    adapter = MarketIntelligenceWorldStateAdapter()
    state = WorldStateV1(schema_version=1, user={'u': 1}, session={'s': 1}, product={'p': 1}, economy={'e': 1}, timestamp_ms=1, tenant_id='t1', meta={'x': 1}, capital=10.0)
    updated = adapter.inject(world_state=state, payload={'provider': 'amazon', 'source_family': 'marketplace', 'records': [{'external_id': '1'}]})
    assert updated.meta['x'] == 1
    assert updated.meta['market_intelligence']['marketplace']['provider'] == 'amazon'
    assert updated.capital == 10.0


def test_recovery_replay_hit_detected(tmp_path: Path) -> None:
    store = SqliteMarketIntelligenceStateStore(db_path=tmp_path / 'state.sqlite3')
    recovery = MarketIntelligenceRecoveryController(state_store=store)
    checkpoint = SyncCheckpoint('t1', 'amazon', 'marketplace', 'q1', 'c1', None, 'sum1', metadata={})
    store.begin_run(run_id='r1', tenant_id='t1', provider='amazon', source_family='marketplace', scope_key='q1', operation='sync_catalog', replay_key='rk1', checkpoint_before=checkpoint, metadata={})
    store.finish_run(run_id='r1', status='succeeded', checkpoint_after=checkpoint, records_count=1, pages_fetched=1)
    verdict = recovery.preflight(tenant_id='t1', provider='amazon', source_family='marketplace', scope_key='q1', operation='sync_catalog', request_fingerprint='fp1')
    assert verdict.replay_hit is False
    replay_key = recovery.replay_key(tenant_id='t1', provider='amazon', source_family='marketplace', scope_key='q1', operation='sync_catalog', request_fingerprint='fp2')
    store.begin_run(run_id='r2', tenant_id='t1', provider='amazon', source_family='marketplace', scope_key='q1', operation='sync_catalog', replay_key=replay_key, checkpoint_before=checkpoint, metadata={})
    store.finish_run(run_id='r2', status='succeeded', checkpoint_after=checkpoint, records_count=1, pages_fetched=1)
    verdict2 = recovery.preflight(tenant_id='t1', provider='amazon', source_family='marketplace', scope_key='q1', operation='sync_catalog', request_fingerprint='fp2')
    assert verdict2.replay_hit is True


def test_runtime_factory_bootstrap_has_manifests() -> None:
    factory = ProviderRuntimeFactory()
    manifest = factory.registry.manifest('amazon')
    assert manifest.source_family == 'marketplace'
