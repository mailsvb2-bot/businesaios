from __future__ import annotations

import bootstrap.boot_context as bootstrap_boot_context
import bootstrap.compose as bootstrap_compose
import bootstrap.process_hygiene as bootstrap_process_hygiene
import bootstrap.prod_guards as bootstrap_prod_guards
import entrypoints.api.fastapi_app_factory as entry_fastapi_factory
import entrypoints.api.runtime_api_bundle as entry_runtime_bundle
import interfaces.api.fastapi_app_factory as legacy_fastapi_factory
import interfaces.api.runtime_api_bundle as legacy_runtime_bundle
import runtime.boot.boot_context as legacy_boot_context
import runtime.bootstrap_process as legacy_process_hygiene
import runtime.bootstrap_prod_guards as legacy_prod_guards


def test_boot_context_final_owner_matches_legacy_exports() -> None:
    assert legacy_boot_context.BootContext is bootstrap_boot_context.BootContext
    assert legacy_boot_context.BootPipeline is bootstrap_boot_context.BootPipeline


def test_runtime_process_hygiene_is_now_owned_by_bootstrap() -> None:
    assert legacy_process_hygiene.apply_process_hygiene is bootstrap_process_hygiene.apply_process_hygiene
    assert legacy_prod_guards.enforce_production_strict_mode is bootstrap_prod_guards.enforce_production_strict_mode


def test_api_entrypoint_owner_matches_legacy_exports() -> None:
    assert legacy_fastapi_factory.create_fastapi_app is entry_fastapi_factory.create_fastapi_app
    assert legacy_runtime_bundle.build_runtime_api_bundle is entry_runtime_bundle.build_runtime_api_bundle


def test_bootstrap_compose_surface_exists() -> None:
    assert bootstrap_compose.CANON_BOOTSTRAP_FINAL_OWNER is True
