from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_no_raw_network_outside_sealed_zone_for_market_intelligence_runtime() -> None:
    forbidden = ('import requests', 'import httpx', 'import aiohttp', 'from requests', 'from httpx', 'import socket')
    scanned = 0
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if 'market_intelligence' not in rel:
            continue
        scanned += 1
        text = _read(path)
        if rel.startswith('runtime/_internal/market_intelligence/') or rel.startswith('tests/'):
            continue
        for marker in forbidden:
            assert marker not in text, f'forbidden raw network import outside sealed zone: {rel} -> {marker}'
    assert scanned >= 20


def test_provider_contract_registry_is_single_source_of_truth() -> None:
    path = ROOT / 'runtime' / '_internal' / 'market_intelligence' / 'provider_contracts.py'
    text = _read(path)
    assert 'class ProviderContractRegistry' in text
    assert 'validate_no_hidden_fallback' in text
    assert 'hidden fallback path is forbidden' in text


def test_derived_governance_blocks_decision_payload() -> None:
    path = ROOT / 'execution' / 'market_intelligence_derived_evidence_governance.py'
    text = _read(path)
    assert 'assert_not_decision_payload' in text
    assert 'decision_core' in text.lower()
    assert 'hidden ranking heuristics are forbidden' in text


def test_provider_client_uses_durable_state_store_and_recovery() -> None:
    path = ROOT / 'runtime' / '_internal' / 'market_intelligence' / 'provider_clients.py'
    text = _read(path)
    assert 'SqliteMarketIntelligenceStateStore' in text
    assert 'MarketIntelligenceRecoveryController' in text
    assert 'begin_run' in text
    assert 'finish_run' in text
    assert 'quarantine_poisoned_source' in text


def test_memory_bridge_is_policy_controlled() -> None:
    path = ROOT / 'execution' / 'market_intelligence_business_memory_bridge.py'
    text = _read(path)
    assert 'memory_policy_controlled' in text
    assert 'MarketIntelligenceDerivedEvidenceGovernance' in text
    assert 'MarketIntelligenceMemoryDiscipline' in text


def test_world_state_adapter_uses_replace_not_manual_reconstruction() -> None:
    path = ROOT / 'execution' / 'market_intelligence_world_state_adapter.py'
    text = _read(path)
    assert 'replace(' in text



def test_operator_control_plane_is_persistence_backed() -> None:
    path = ROOT / 'execution' / 'market_intelligence_operator_control_plane.py'
    text = _read(path)
    assert 'PersistentMarketIntelligenceOperatorStore' in text
    assert 'store:' in text


def test_compliance_boundary_is_storage_backed() -> None:
    path = ROOT / 'execution' / 'market_intelligence_compliance_boundary.py'
    text = _read(path)
    assert 'PersistentMarketIntelligenceComplianceStore' in text
    assert 'upsert_provider_policy' in text


def test_scheduler_boot_exists_without_decision_core_reference() -> None:
    path = ROOT / 'runtime' / 'boot' / 'market_intelligence_boot.py'
    text = _read(path)
    assert 'build_market_intelligence_runtime' in text
    assert 'DecisionCore' not in text


def test_scheduler_service_uses_lease_store_not_hidden_decision_logic() -> None:
    path = ROOT / 'execution' / 'market_intelligence_scheduler_service.py'
    text = _read(path)
    assert 'PersistentMarketIntelligenceScheduleLeaseStore' in text
    assert 'schedule_lease_held' in text
    assert 'DecisionCore' not in text


def test_observability_store_is_persistence_only() -> None:
    path = ROOT / 'execution' / 'market_intelligence_observability_store.py'
    text = _read(path)
    assert 'Persistence only' in text
    assert 'DecisionCore' not in text
    assert 'append_run' in text
    assert 'append_anomaly' in text


def test_scheduler_coordination_uses_reliability_lock_not_decision_logic() -> None:
    path = ROOT / 'execution' / 'market_intelligence_scheduler_coordination.py'
    text = _read(path)
    assert 'LeaderElection' in text
    assert 'LeaseManager' in text
    assert 'DecisionCore' not in text
    assert 'planning' in text.lower()


def test_market_intelligence_runtime_support_reuses_shared_runtime_reliability() -> None:
    path = ROOT / 'runtime' / 'market_intelligence_runtime_support.py'
    text = _read(path)
    assert 'build_executor_recovery_support' in text
    assert 'scheduler_leader_election' in text
    assert 'DecisionCore' not in text


def test_scheduler_service_accepts_shared_scheduler_leader_election() -> None:
    path = ROOT / 'execution' / 'market_intelligence_scheduler_service.py'
    text = _read(path)
    assert 'scheduler_leader_election' in text
    assert 'MarketIntelligenceSchedulerCoordination' in text
    assert 'DecisionCore' not in text


def test_scheduler_supervisor_declares_no_decision_logic() -> None:
    path = ROOT / "execution" / "market_intelligence_scheduler_supervisor.py"
    text = _read(path)
    assert "CANON_MARKET_INTELLIGENCE_SCHEDULER_SUPERVISOR_NO_DECISION_LOGIC" in text
    assert "alternate decision path" in text.lower()


def test_runtime_registry_bridge_and_supervisor_have_no_decision_logic() -> None:
    bridge = ROOT / 'runtime' / 'market_intelligence_runtime_registry_bridge.py'
    bridge_text = _read(bridge)
    assert 'NO_DECISION_LOGIC' in bridge_text
    assert 'DecisionCore' not in bridge_text
    supervisor = ROOT / 'execution' / 'market_intelligence_scheduler_supervisor.py'
    supervisor_text = _read(supervisor)
    assert 'CANON_MARKET_INTELLIGENCE_SCHEDULER_SUPERVISOR_NO_DECISION_LOGIC = True' in supervisor_text
    assert 'DecisionCore' not in supervisor_text


def test_managed_runtime_plane_declares_no_decision_logic() -> None:
    path = ROOT / 'runtime' / 'managed_runtime_plane.py'
    text = _read(path)
    assert 'CANON_MANAGED_RUNTIME_PLANE_NO_DECISION_LOGIC = True' in text
    assert 'alternate decision path' in text.lower()
    assert 'DecisionCore' not in text
