from pathlib import Path


def test_inference_capacity_web_surfaces_are_exported() -> None:
    components_init = Path('app/web/components/__init__.py').read_text(encoding='utf-8')
    pages_init = Path('app/web/pages/__init__.py').read_text(encoding='utf-8')
    assert 'InferenceTierPanel' in components_init
    assert 'InferenceProviderHealthPanel' in components_init
    assert 'InferenceRuntimeAdminPage' in pages_init
    assert 'InferenceCapacityPage' in pages_init


def test_inference_capacity_entrypoint_surfaces_exist() -> None:
    for path in (
        Path('entrypoints/api/inference_capacity_route_handlers.py'),
        Path('entrypoints/api/inference_provider_route_handlers.py'),
        Path('entrypoints/api/inference_admin_route_handlers.py'),
        Path('entrypoints/api/inference_runtime_admin_route_handlers.py'),
    ):
        assert path.exists(), f'missing compat/final-owner entrypoint surface: {path}'
