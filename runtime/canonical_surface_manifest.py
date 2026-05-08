from __future__ import annotations

CANONICAL_BOOTSTRAP_OWNER_MODULES: tuple[str, ...] = (
    "runtime.bootstrap",
    "runtime.bootstrap.sovereign_bootstrap",
)

LEGACY_BOOTSTRAP_COMPAT_MODULES: tuple[str, ...] = (
    "boot",
    "boot.bootstrap",
    "boot.runtime_boot",
    "crm.public_api",
    "boot.public_api",
    "boot.facade",
    "boot.runtime_public_api",
    "boot.app_boot",
    "boot.app_boot_surface",
    "boot.app_public_api",
    "boot.http_boot",
    "boot.http_public_api",
    "boot.telegram_boot",
    "boot.connectors_boot",
    "boot.contracts_boot",
    "boot.execution_boot",
    "boot.feedback_boot",
    "boot.observability_boot",
    "boot.system_registry_boot",
)

ALLOWED_BOOTSTRAP_COMPAT_IMPORTERS: tuple[str, ...] = (
    "boot/public_api.py",
    "execution/headless_boot.py",
    "runtime/bootstrap.py",
    "runtime/runtime_boot.py",
    "runtime/boot/system_builder.py",
    "runtime/entrypoints/telegram_longpoll.py",
    "bootstrap/platform_boot_surface.py",
    "bootstrap/runtime_boot.py",
)

CANONICAL_OWNER_PUBLIC_APIS: tuple[str, ...] = (
    "boot",
    "core.decision",
    "crm",
    "execution",
    "runtime.application",
    "runtime.state",
    "runtime.world_state",
)

COMPATIBILITY_PUBLIC_APIS: tuple[str, ...] = (
    "runtime.application.public_api",
    "runtime.state.public_api",
    "runtime.world_state.public_api",
    "runtime.world_model.public_api",
    "runtime.tenancy.public_api",
    "runtime.finance.public_api",
    "runtime.human_governance.public_api",
    "runtime.knowledge.public_api",
    "runtime.proofs.public_api",
    "runtime.safety.public_api",
    "core.decision.public_api",
    "execution.public_api",
    "crm.public_api",
    "boot.public_api",
    "boot.app_public_api",
    "boot.http_public_api",
    "boot.runtime_public_api",
    "headless",
)

ALLOWED_EFFECT_ROUTER_IMPORTERS: tuple[str, ...] = (
    "runtime/_internal/router_support.py",
    "runtime/execution/executor_state.py",
)

ALLOWED_EFFECT_DOMAIN_ENTRYPOINTS: tuple[str, ...] = (
    "runtime/_internal/effect_router.py",
    "runtime/_internal/router_support.py",
    "runtime/_internal/effects_actions/",
    "runtime/_internal/effects_clients/",
)

ALLOWED_NETWORK_PRIMITIVE_IMPORTERS: tuple[str, ...] = (
    "runtime/_internal/http_transport.py",
    "runtime/_internal/market_intelligence/http_transport.py",
    "runtime/security/ast_bypass_guard.py",
    "runtime/business_autonomy/provider_http_live_clients.py",
    "runtime/business_autonomy/provider_vendor_transports.py",
)

ALLOWED_NETWORK_LITERAL_SURFACES: tuple[str, ...] = (
    "runtime/_internal/_effects_impl.py",
    "runtime/_internal/effects_clients/telegram_client.py",
    "runtime/_internal/effects_clients/yookassa_client.py",
    "runtime/_internal/effects_clients/yookassa_webhook_server.py",
    "runtime/_internal/effects_actions/telegram/startup.py",
    "runtime/_internal/effects_actions/telegram_actions_polling.py",
    "runtime/_internal/effect_router.py",
    "runtime/_internal/effect_types.py",
    "runtime/_internal/effect_payloads.py",
    "runtime/_internal/effects_actions/payments/yookassa.py",
    "runtime/business_autonomy/provider_http_live_clients.py",
    "runtime/business_autonomy/provider_transport_bindings.py",
    "runtime/business_autonomy/provider_vendor_transports.py",
)

CANONICAL_ROUTE_OWNER_MODULES: tuple[str, ...] = (
    "execution.routing.capability_router",
    "execution.routing.capability_registry",
    "execution.routing.fallback_tree",
)

EVIDENCE_ONLY_ROUTE_HELPERS: tuple[str, ...] = (
    "execution.routing.route_continuity_memory",
    "execution.routing.route_explainer",
    "execution.routing.capability_health_scoring",
    "execution.routing.capability_cost_model",
    "execution.routing.capability_latency_model",
    "execution.routing.capability_proofability_score",
)


CANONICAL_PACKAGE_OWNER_SURFACES: tuple[str, ...] = (
    "boot.factories",
    "boot.registrations",
    "config",
    "core.actions",
    "execution.effectors",
    "marketplace",
    "observability",
    "app.web.components",
    "app.web.pages",
    "runtime.application",
    "runtime.bootstrap",
    "runtime.ai_ceo",
    "runtime.behavior",
    "runtime.canon",
    "runtime.decision_input",
    "runtime.enforcement",
    "runtime.explainability",
    "runtime.growth",
    "runtime.learning_loop",
    "runtime.llm",
    "runtime.marketing",
    "runtime.ml",
    "runtime.monetization",
    "runtime.pricing",
    "runtime.product",
    "runtime.queue",
    "runtime.recovery_support",
    "runtime.revenue",
    "runtime.reward",
    "runtime.security",
    "runtime.time",
    "tenancy",
    "observability",
)
