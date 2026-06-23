from __future__ import annotations

CANON_ECONOMIC_SEALED_EXECUTION_LOCK = True
ALLOWED_RUNTIME_INTERNAL_IMPORT_OWNERS = (
    'runtime/executor.py',
    'runtime/_internal/economic_execution_contract.py',
    'tests/arch/test_economic_sealed_execution_owner_lock_wave239.py',
    'tests/arch/test_economic_sealed_execution_hardening_wave240.py',
    'tests/arch/test_economic_sealed_execution_repo_sweep_wave241.py',
)
FORBIDDEN_SECOND_BRAIN_MARKERS = (
    'click_provider_execute_direct',
    'spend_ingress_execute_direct',
    'manual provider dispatch outside sealed execution gateway',
)
SEALED_EXECUTION_ROUTE_PATHS = (
    '/economic/truth/click-billing-sealed-execution/{order_id}/{lead_id}',
    '/economic/export/click-billing-sealed-execution/{order_id}/{lead_id}',
    '/economic/audit/click-billing-sealed-execution/{order_id}/{lead_id}',
    '/economic/truth/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}',
    '/economic/export/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}',
    '/economic/audit/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}',
)
FORBIDDEN_RUNTIME_INTERNAL_IMPORTERS = (
    'entrypoints/api/economic_route_handlers.py',
    'entrypoints/api/economic_routes/payloads.py',
    'entrypoints/api/economic_routes/client_outcome.py',
    'entrypoints/api/economic_routes/business.py',
    'entrypoints/api/economic_routes/click.py',
    'entrypoints/api/economic_routes/spend.py',
    'entrypoints/api/economic_routes/click_ops_billing_post.py',
    'entrypoints/api/economic_routes/click_ops_core.py',
    'entrypoints/api/economic_routes/spend_ops_core.py',
    'entrypoints/api/economic_routes/spend_ops_ingress.py',
    'adapters/api/fastapi/public_routes.py',
    'adapters/api/fastapi/public_route_groups/core_and_economic.py',
    'click_economics/public_api.py',
    'spend/public_api.py',
)


ALLOWED_EXECUTION_GATEWAY_IMPORTERS = (
    'entrypoints/api/economic_route_handlers.py',
    'entrypoints/api/economic_routes/payloads.py',
    'entrypoints/api/economic_routes/client_outcome.py',
    'entrypoints/api/economic_routes/business.py',
    'entrypoints/api/economic_routes/click.py',
    'entrypoints/api/economic_routes/spend.py',
    'tests/arch/test_economic_sealed_execution_owner_lock_wave239.py',
    'tests/arch/test_economic_sealed_execution_repo_sweep_wave241.py',
    'tests/unit/client_outcome/test_click_and_spend_truth_fragments.py',
)
FORBIDDEN_EXECUTION_GATEWAY_IMPORTERS = (
    'adapters/api/fastapi/public_routes.py',
    'adapters/api/fastapi/public_route_groups/core_and_economic.py',
    'entrypoints/api/public_surface_security_guard.py',
    'click_economics/public_api.py',
    'spend/public_api.py',
)
FORBIDDEN_DIRECT_SEALED_RUNTIME_MARKERS = (
    'sealed_click_execution_contract_materialized',
    'sealed_spend_execution_contract_materialized',
)


ALLOWED_SEALED_EXECUTION_HELPER_OWNERS = (
    'runtime/executor.py',
    'runtime/_internal/economic_execution_contract.py',
    'entrypoints/api/economic_route_handlers.py',
    'entrypoints/api/economic_routes/payloads.py',
    'entrypoints/api/economic_routes/client_outcome.py',
    'entrypoints/api/economic_routes/business.py',
    'entrypoints/api/economic_routes/click.py',
    'entrypoints/api/economic_routes/spend.py',
    'tests/arch/test_economic_sealed_execution_owner_lock_wave239.py',
    'tests/arch/test_economic_sealed_execution_repo_sweep_wave241.py',
    'tests/arch/test_economic_sealed_execution_ultra_repo_sweep_wave242.py',
    'tests/unit/client_outcome/test_click_and_spend_truth_fragments.py',
    'entrypoints/api/economic_routes/click_ops_billing_post.py',
    'entrypoints/api/economic_routes/click_ops_core.py',
    'entrypoints/api/economic_routes/spend_ops_core.py',
    'entrypoints/api/economic_routes/spend_ops_ingress.py',
)
ALLOWED_SEALED_ROUTE_MARKER_OWNERS = (
    'lock/economic_sealed_execution_lock.py',
    'entrypoints/api/public_surface_security_guard.py',
    'adapters/api/fastapi/public_routes.py',
    'adapters/api/fastapi/public_route_groups/core_and_economic.py',
    'tests/arch/test_economic_sealed_execution_owner_lock_wave239.py',
    'tests/arch/test_economic_sealed_execution_hardening_wave240.py',
    'tests/arch/test_economic_sealed_execution_ultra_repo_sweep_wave242.py',
    'entrypoints/api/public_surface_security_specs.py',
)
FORBIDDEN_GATEWAY_IMPORT_PREFIXES = (
    'api/',
    'app/',
    'billing/',
    'boot/',
    'click_economics/',
    'connectors/',
    'economics/',
    'spend/',
)
