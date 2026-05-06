from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_headless_runtime_provider_is_single_owner_surface() -> None:
    text = _text('entrypoints/api/headless_runtime_provider.py')
    assert 'CANON_API_HEADLESS_RUNTIME_PROVIDER = True' in text
    assert 'CANON_API_HEADLESS_RUNTIME_PROVIDER_SINGLE_OWNER = True' in text
    assert 'def build_headless_runtime_provider(' in text


def test_headless_and_business_memory_handlers_use_shared_runtime_provider() -> None:
    headless = _text('entrypoints/api/headless_route_handlers.py')
    business_memory = _text('entrypoints/api/business_memory_route_handlers.py')
    assert 'HeadlessRuntimeProvider' in headless
    assert 'build_default_headless_runtime_provider' in headless
    assert 'build_headless_runtime()' not in headless
    assert 'HeadlessRuntimeProvider' in business_memory
    assert 'build_default_headless_runtime_provider' in business_memory
    assert 'build_headless_runtime()' not in business_memory


def test_api_handler_bundle_reuses_one_headless_runtime_provider_for_api_read_surfaces() -> None:
    text = _text('entrypoints/api/api_handler_bundle.py')
    assert 'runtime_provider = headless_runtime_provider or build_default_headless_runtime_provider()' in text
    assert 'build_headless_route_handlers(runtime_provider=runtime_provider)' in text
    assert 'build_business_memory_route_handlers(runtime_provider=runtime_provider)' in text


def test_fastapi_router_uses_runtime_bundle_instead_of_building_read_surface_runtime_directly() -> None:
    text = _text('adapters/api/fastapi/router_adapter.py')
    assert 'runtime_api_bundle = build_runtime_api_bundle(' in text
    assert 'handler_bundle = runtime_api_bundle.handler_bundle' in text
    assert 'build_headless_runtime()' not in text
