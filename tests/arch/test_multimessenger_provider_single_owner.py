from __future__ import annotations

import ast
from pathlib import Path

from application.business_autonomy.provider_catalog import provider_map

ROOT = Path(__file__).resolve().parents[2]

OWNERS = {
    'ProviderQueueExecutionRuntime': 'runtime/business_autonomy/provider_queue_execution.py',
    'ProviderPacingCoordinator': 'runtime/business_autonomy/provider_pacing.py',
    'ProviderMediaPreparationCoordinator': 'runtime/business_autonomy/provider_media.py',
    'ProviderWebhookReconciler': 'runtime/business_autonomy/provider_webhook_reconciliation.py',
    'ProviderWebhookOperationalResponder': 'runtime/business_autonomy/provider_webhook_reconciliation.py',
}

HELPERS = (
    'runtime/business_autonomy/provider_pacing.py',
    'runtime/business_autonomy/provider_media.py',
    'runtime/business_autonomy/provider_max_media_http.py',
    'runtime/business_autonomy/provider_vk_media_http.py',
    'runtime/business_autonomy/provider_webhook_reconciliation.py',
)


def _class_owners(name: str) -> list[str]:
    owners: list[str] = []
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith('tests/'):
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        if any(isinstance(node, ast.ClassDef) and node.name == name for node in ast.walk(tree)):
            owners.append(rel)
    return owners


def test_multimessenger_operational_semantics_have_one_owner_each() -> None:
    for name, owner in OWNERS.items():
        assert _class_owners(name) == [owner], (name, _class_owners(name))


def test_provider_helpers_do_not_grow_a_second_queue_or_decision_runtime() -> None:
    forbidden_prefixes = ('runtime.queue', 'execution', 'governance', 'runtime.decision', 'core.decision')
    offenders = []
    for rel in HELPERS:
        tree = ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and str(node.module or '').startswith(forbidden_prefixes):
                offenders.append((rel, node.module))
    assert offenders == []


def test_provider_helpers_do_not_open_their_own_network_stack() -> None:
    forbidden_modules = {'urllib', 'urllib.request', 'http.client', 'requests', 'httpx', 'aiohttp', 'socket'}
    offenders = []
    for rel in HELPERS:
        tree = ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders.extend((rel, alias.name) for alias in node.names if alias.name in forbidden_modules)
            elif isinstance(node, ast.ImportFrom) and str(node.module or '') in forbidden_modules:
                offenders.append((rel, node.module))
    assert offenders == []


def test_binary_network_owner_remains_sealed_http_transport() -> None:
    owners = []
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith('tests/'):
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if 'def sync_multipart_file(' in text:
            owners.append(rel)
    assert owners == ['runtime/_internal/http_transport.py']


def test_vk_max_capability_truth_matches_canonical_transport() -> None:
    providers = provider_map()
    assert providers['vk_messaging'].messaging_capabilities == {
        'plain_text': True, 'buttons': True, 'attachments': True,
    }
    assert providers['max_messaging'].messaging_capabilities == {
        'plain_text': True, 'attachments': True,
    }


def test_provider_queue_is_the_only_durable_native_send_owner() -> None:
    queue_source = (ROOT / 'runtime/business_autonomy/provider_queue_execution.py').read_text(encoding='utf-8')
    bridge_source = (ROOT / 'runtime/messaging/bootstrap.py').read_text(encoding='utf-8')
    assert 'CANON_PROVIDER_QUEUE_EXECUTION = True' in queue_source
    assert 'JobDispatcher(' in queue_source and 'JobWorker(' in queue_source
    assert 'ProviderQueueExecutionRuntime' not in bridge_source
    assert 'execute_queued_provider_sync' in bridge_source


def test_media_and_pacing_helpers_are_operational_projections_only() -> None:
    pacing = (ROOT / 'runtime/business_autonomy/provider_pacing.py').read_text(encoding='utf-8')
    media = (ROOT / 'runtime/business_autonomy/provider_media.py').read_text(encoding='utf-8')
    assert 'SQLiteDistributedCompareAndSwap' not in pacing
    assert 'SQLiteDistributedCompareAndSwap' not in media
    assert 'compare_and_swap' in pacing
    assert 'compare_and_swap' in media
    assert 'time.sleep' not in pacing + media


def test_webhook_reconciliation_uses_existing_route_and_transport_binding_owners() -> None:
    source = (ROOT / 'runtime/business_autonomy/provider_webhook_reconciliation.py').read_text(encoding='utf-8')
    assert 'ProviderWebhookRouteRegistry' in source
    assert 'ProviderTransportBindings' in source
    assert "import_internal_attr('runtime._internal.http_transport', 'sync_request')" in source
    assert 'api.telegram.org' not in source
    assert 'api.vk.com' not in source
    assert 'platform-api2.max.ru' not in source
