from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_module_registry_has_owner_builder() -> None:
    text = _read("runtime/modules/registry.py")
    assert "CANON_RUNTIME_MODULE_REGISTRY_OWNER = True" in text
    assert "def build_runtime_module_registry(" in text



def test_runtime_builtin_catalog_has_owner_builder_and_shared_defaults() -> None:
    text = _read("runtime/modules/builtin_modules.py")
    assert "CANON_RUNTIME_MODULE_CATALOG_OWNER = True" in text
    assert "DEFAULT_RUNTIME_MODULE_IDS" in text
    assert "def build_builtin_runtime_modules(" in text
    assert "build_decision_service_descriptor(" in text



def test_product_system_builder_pipeline_uses_shared_builtin_ids() -> None:
    text = _read("runtime/boot/product_system_builder_pipeline.py")
    assert "CANON_PRODUCT_SYSTEM_WIRING_ADAPTER_OWNER = True" in text
    assert "DEFAULT_RUNTIME_MODULE_IDS" in text
    assert "for module_id in DEFAULT_RUNTIME_MODULE_IDS" in text
    assert 'RuntimeServiceName.DECISION_CORE' not in text



def test_product_system_builder_uses_runtime_module_builders() -> None:
    text = _read("runtime/boot/product_system_builder.py")
    assert "build_builtin_runtime_modules" in text
    assert "build_runtime_module_registry" in text
    assert "build_product_system_wiring_adapter" in text
    assert "ModuleRegistry(load_builtin_modules())" not in text
