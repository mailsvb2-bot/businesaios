from __future__ import annotations

import inspect
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response, status

from adapters.api.fastapi.analytics_routes import register_analytics_routes
from adapters.api.fastapi.business_workspace_acquisition_routes import register_business_workspace_acquisition_routes
from adapters.api.fastapi.business_workspace_commercial_routes import register_business_workspace_commercial_routes
from adapters.api.fastapi.business_workspace_decision_routes import register_business_workspace_decision_routes
from adapters.api.fastapi.business_workspace_discovery_routes import register_business_workspace_discovery_routes
from adapters.api.fastapi.business_workspace_event_landing_routes import (
    register_business_workspace_event_landing_routes,
)
from adapters.api.fastapi.business_workspace_process_routes import register_business_workspace_process_routes
from adapters.api.fastapi.business_workspace_program_routes import register_business_workspace_program_routes
from adapters.api.fastapi.business_workspace_provider_routes import register_business_workspace_provider_routes
from adapters.api.fastapi.business_workspace_support_case_routes import register_business_workspace_support_case_routes
from adapters.api.fastapi.public_client_outcome_routes import register_public_client_outcome_routes
from adapters.api.fastapi.public_core_routes import register_public_core_routes
from adapters.api.fastapi.public_site_routes import (
    _cta_status_response,
    _cta_submit_response,
    register_public_site_routes,
)
from adapters.api.fastapi.router_support import authorize_request
from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.support_case_registry import SupportCaseRegistry
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.public_site.event_landing_registry import EventLandingRegistry
from crm.customer_registry import CustomerRegistry
from entrypoints.api.owner_action_draft import OwnerActionDraftProjector
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers
from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.request_context import RequestContext
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime

CANON_FASTAPI_PUBLIC_ROUTES_FINAL_OWNER = True
CANON_PRODUCTION_GUARD_PRINCIPAL_CONTRACT_REQUIRED = True


def _is_test_guard(security_guard: PublicSurfaceSecurityGuard) -> bool:
    source_file = inspect.getsourcefile(type(security_guard))
    if not source_file:
        return False
    return 'tests' in Path(source_file).resolve().parts


def _enforce_security_guard(
    *,
    security_guard: PublicSurfaceSecurityGuard,
    route_path: str,
    request_context: RequestContext,
    body: dict | None,
    principal,
) -> None:
    enforce_parameters = inspect.signature(security_guard.enforce).parameters
    if 'principal' in enforce_parameters:
        security_guard.enforce(
            route_path=route_path,
            request_context=request_context,
            body=body,
            principal=principal,
        )
        return
    if not _is_test_guard(security_guard):
        raise PermissionError('api_security_guard_principal_contract_required')
    security_guard.enforce(
        route_path=route_path,
        request_context=request_context,
        body=body,
    )


def register_public_api_routes(
    *,
    router: APIRouter,
    dependency_container,
    health_handler,
    handlers,
    headless_handlers,
    governance_handlers,
    business_memory_handlers,
    governance_advanced_handlers,
    security_guard: PublicSurfaceSecurityGuard,
    auth_bundle=None,
    tenant_registry=None,
    analytics_handlers=None,
    client_outcome_handlers=None,
    economic_handlers=None,
    process_workspace=None,
    process_request_idempotency=None,
    business_discovery_workspace=None,
    commercial_payment_adapter=None,
    commercial_payment_verifier=None,
    commercial_reversal_reader=None,
    commercial_merchant_id=None,
) -> None:
    if tenant_registry is None and dependency_container is not None:
        tenant_registry = getattr(dependency_container, 'tenant_registry', None)

    def enforce_public_security(
        *,
        route_path: str,
        request_context: RequestContext,
        body: dict | None = None,
        http_request: Request | None = None,
    ) -> RequestContext:
        try:
            principal = None
            if security_guard.requires_external_auth(route_path):
                if auth_bundle is None:
                    raise PermissionError('api_perimeter_auth_unconfigured')
                if http_request is None:
                    raise PermissionError('api_perimeter_request_required')
                request_context, principal = authorize_request(request=http_request, auth_bundle=auth_bundle)
                principal_metadata = dict(getattr(principal, 'metadata', {}) or {})
                principal_business_id = str(principal_metadata.get('business_id') or '').strip()
                principal_kind = str(principal_metadata.get('principal_kind') or '').strip().lower()
                authenticated_agent_id = (
                    str(getattr(principal, 'actor_id', None) or getattr(principal, 'subject', '') or '').strip()
                    if principal_kind == 'service'
                    else ''
                )
                request_context = request_context.with_metadata(
                    route=route_path,
                    **({'authenticated_business_id': principal_business_id} if principal_business_id else {}),
                    **({'authenticated_agent_id': authenticated_agent_id} if authenticated_agent_id else {}),
                )
            _enforce_security_guard(
                security_guard=security_guard,
                route_path=route_path,
                request_context=request_context,
                body=body,
                principal=principal,
            )
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return request_context

    def authenticated_tenant(request_context: RequestContext) -> str:
        tenant_id = request_context.validated_tenant_id(required=True)
        assert tenant_id is not None
        return tenant_id

    def raise_boundary_error(exc: Exception) -> None:
        if isinstance(exc, PermissionError):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        if isinstance(exc, KeyError):
            detail = str(exc.args[0] if exc.args else 'not_found')
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise exc

    headless_runtime_provider = getattr(headless_handlers, 'runtime_provider', None)
    owner_action_draft_projector = (
        OwnerActionDraftProjector(runtime_provider=headless_runtime_provider)
        if headless_runtime_provider is not None
        else None
    )

    register_public_core_routes(
        router=router,
        health_handler=health_handler,
        handlers=handlers,
        headless_handlers=headless_handlers,
        governance_handlers=governance_handlers,
        business_memory_handlers=business_memory_handlers,
        governance_advanced_handlers=governance_advanced_handlers,
        enforce_public_security=enforce_public_security,
        owner_action_draft_projector=owner_action_draft_projector,
    )
    if dependency_container is not None:
        @router.get('/providers/webhook/{tenant_id}/{business_id}/{provider_key}', tags=['provider-runtime'])
        async def provider_webhook_challenge(tenant_id: str, business_id: str, provider_key: str, request: Request) -> Response:
            provider = provider_map().get(provider_key)
            if provider is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='provider_not_found')
            challenge = ProviderWebhookRuntime(dependency_container.secret_vault).verify_challenge(
                provider=provider,
                tenant_id=tenant_id,
                business_id=business_id,
                mode=request.query_params.get('hub.mode', ''),
                verify_token=request.query_params.get('hub.verify_token', ''),
                challenge=request.query_params.get('hub.challenge', ''),
            )
            if challenge is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='provider_webhook_challenge_denied')
            return Response(content=challenge, media_type='text/plain')
    event_landing_registry = None
    if dependency_container is not None and getattr(dependency_container, 'api_idempotency_store', None) is not None:
        event_store = dependency_container.canonical_business_event_store()
        if event_store is not None:
            event_landing_registry = EventLandingRegistry(
                event_store=event_store,
                idempotency_store=dependency_container.api_idempotency_store,
            )
    register_public_site_routes(
        router=router, enforce_public_security=enforce_public_security,
        auth_bundle=auth_bundle, tenant_registry=tenant_registry,
        event_landing_registry=event_landing_registry,
    )
    if auth_bundle is not None:
        if business_discovery_workspace is not None:
            register_business_workspace_discovery_routes(
                router=router,
                auth_bundle=auth_bundle,
                workspace=business_discovery_workspace,
            )
        # The owner CRM view and program enrollment share the exact Customer
        # registry/event spine. No shadow customer, provider or decision owner.
        canonical_customers = (
            CustomerRegistry(
                event_store=event_store,
                idempotency_store=dependency_container.api_idempotency_store,
                pii_vault=dependency_container.secret_vault,
            ) if event_landing_registry is not None else None
        )
        provider_handlers = ProviderAdminRouteHandlers(
            customer_event_store=event_store if canonical_customers is not None else None,
            customer_registry=canonical_customers,
        )
        register_business_workspace_provider_routes(
            router=router, auth_bundle=auth_bundle, provider_admin_handlers=provider_handlers,
        )
        if dependency_container is not None and getattr(dependency_container, "api_idempotency_store", None) is not None:
            # Canonical event/idempotency owners only: never invent an isolated
            # support ledger if the application has no durable Event Spine.
            support_event_store = dependency_container.canonical_business_event_store()
            if support_event_store is not None:
                register_business_workspace_support_case_routes(
                    router=router, auth_bundle=auth_bundle,
                    support_cases=SupportCaseRegistry(
                        event_store=support_event_store,
                        idempotency_store=dependency_container.api_idempotency_store,
                    ),
                )
        if event_landing_registry is not None:
            from application.commerce.phase18_commercial_context import CommercialJourneyContextReader
            from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
            from application.lead.registry import LeadRegistry
            from billing.invoice_registry import InvoiceRegistry
            from core.offers.offer_catalog_resolver import OfferCatalogResolver
            from lead_outcomes.client_outcome_order_store import OrderStore
            from runtime.messaging.conversation_registry import ConversationRegistry
            from runtime.messaging.message_registry import MessageRegistry
            from runtime.platform.client_outcome_persistence import ClientOutcomePersistenceOwner

            canonical_programs = ProgramPublicationRegistry(
                event_store=event_store,
                idempotency_store=dependency_container.api_idempotency_store,
                customer_registry=canonical_customers,
            )
            commercial_purchases = CommercialProgramPurchaseService(
                leads=LeadRegistry(event_store=event_store, idempotency_store=dependency_container.api_idempotency_store),
                customers=canonical_customers,
                programs=canonical_programs,
                offers=OfferCatalogResolver(),
                orders=OrderStore(
                    backend=ClientOutcomePersistenceOwner.default().registry("order"),
                    event_store=event_store, require_event_spine=True,
                ),
                invoices=InvoiceRegistry(event_store=event_store, idempotency_store=dependency_container.api_idempotency_store),
            )
            # Configure the *existing* checkout and Billing owners only when
            # all external money and reversal authorities are explicitly supplied
            # by server bootstrap. Partial configuration is a startup error.
            from runtime.platform.config.env_flags import env_str

            commercial_yookassa_opt_in = env_str(
                "BUSINESAIOS_COMMERCIAL_PSP_ENABLED", "0",
            ).strip().lower() in {"1", "true", "yes", "on"}
            commercial_stars_opt_in = env_str(
                "BUSINESAIOS_COMMERCIAL_STARS_ENABLED", "0",
            ).strip().lower() in {"1", "true", "yes", "on"}
            if (commercial_yookassa_opt_in or commercial_stars_opt_in) and any(
                part is not None for part in (
                    commercial_payment_adapter, commercial_payment_verifier,
                    commercial_reversal_reader, commercial_merchant_id,
                )
            ):
                raise RuntimeError("commercial_conflicting_payment_authorities")
            commercial_provider_parts = (
                commercial_payment_adapter, commercial_payment_verifier,
                commercial_reversal_reader, commercial_merchant_id,
            )
            if any(part is not None for part in commercial_provider_parts) and not all(
                part is not None for part in commercial_provider_parts
            ):
                raise RuntimeError("commercial_payment_authorities_incomplete")
            commercial_checkout = None
            commercial_settlement = None
            if all(part is not None for part in commercial_provider_parts):
                from application.commerce.phase18_commercial_access import CanonicalPaidProgramAccess
                from application.commerce.phase18_commercial_checkout import CommercialCheckoutCoordinator
                from billing.phase18_commercial_settlement import CommercialSettlementReconciler

                commercial_checkout = CommercialCheckoutCoordinator(
                    purchase_service=commercial_purchases,
                    payment_adapter=commercial_payment_adapter,
                    event_store=event_store,
                    idempotency_store=dependency_container.api_idempotency_store,
                )
                commercial_settlement = CommercialSettlementReconciler(
                    purchases=commercial_purchases, checkouts=commercial_checkout,
                    payment_verifier=commercial_payment_verifier,
                    configured_merchant_id=commercial_merchant_id,
                )
                canonical_programs.bind_paid_access_authority(
                    CanonicalPaidProgramAccess(
                        purchases=commercial_purchases, checkouts=commercial_checkout,
                        reversal_reader=commercial_reversal_reader,
                    )
                )
            if commercial_stars_opt_in:
                from contracts.customer import CustomerIdentityStatus, CustomerStatus
                from runtime.executor_api_support import (
                    build_sealed_dual_commercial_merchant_bundle,
                    build_sealed_stars_commercial_merchant_bundle,
                )

                def canonical_stars_payer(*, tenant_id, business_id, customer_id):
                    customer = canonical_customers.get_customer(
                        tenant_id=tenant_id, business_id=business_id,
                        customer_id=customer_id,
                    )
                    if customer.customer.status is not CustomerStatus.ACTIVE:
                        raise RuntimeError("stars_customer_inactive")
                    identities = [
                        identity for identity in customer.identities
                        if identity.channel == "telegram"
                        and identity.status is CustomerIdentityStatus.ACTIVE
                    ]
                    if len(identities) != 1:
                        raise RuntimeError("stars_telegram_identity_missing_or_ambiguous")
                    subject = identities[0].external_subject
                    if (not isinstance(subject, str) or not subject.isascii()
                            or not subject.isdecimal() or int(subject) < 1):
                        raise RuntimeError("stars_telegram_payer_id_invalid")
                    return int(subject)

                builder = (
                    build_sealed_dual_commercial_merchant_bundle
                    if commercial_yookassa_opt_in
                    else build_sealed_stars_commercial_merchant_bundle
                )
                merchant_bundle = builder(
                    purchases=commercial_purchases, event_store=event_store,
                    idempotency_store=dependency_container.api_idempotency_store,
                    payer_resolver=canonical_stars_payer,
                )
                commercial_checkout = merchant_bundle.checkout
                commercial_settlement = merchant_bundle.settlement
                canonical_programs.bind_paid_access_authority(merchant_bundle.paid_access)
            elif commercial_yookassa_opt_in:
                from runtime.executor_api_support import build_sealed_commercial_merchant_bundle

                merchant_bundle = build_sealed_commercial_merchant_bundle(
                    purchases=commercial_purchases, event_store=event_store,
                    idempotency_store=dependency_container.api_idempotency_store,
                )
                commercial_checkout = merchant_bundle.checkout
                commercial_settlement = merchant_bundle.settlement
                canonical_programs.bind_paid_access_authority(
                    merchant_bundle.paid_access,
                )
            register_business_workspace_program_routes(
                router=router, auth_bundle=auth_bundle,
                provider_admin_handlers=provider_handlers, programs=canonical_programs,
            )
            commercial_context = CommercialJourneyContextReader(
                leads=commercial_purchases.leads,
                customers=canonical_customers,
                conversations=ConversationRegistry(
                    event_store=event_store, idempotency_store=dependency_container.api_idempotency_store,
                    customer_registry=canonical_customers,
                ),
                messages=MessageRegistry(
                    event_store=event_store, idempotency_store=dependency_container.api_idempotency_store,
                ),
                programs=commercial_purchases.programs,
                orders=commercial_purchases.orders,
                invoices=commercial_purchases.invoices,
            )
            from application.partner.registry import PartnerRegistry

            register_business_workspace_commercial_routes(
                router=router, auth_bundle=auth_bundle,
                purchases=commercial_purchases, checkout=commercial_checkout,
                context_reader=commercial_context, settlement=commercial_settlement,
                provider_handlers=provider_handlers, customers=canonical_customers,
                partner_registry=PartnerRegistry(
                    event_store=event_store,
                    idempotency_store=dependency_container.api_idempotency_store,
                ),
            )
        if event_landing_registry is not None:
            register_business_workspace_event_landing_routes(
                router=router, auth_bundle=auth_bundle,
                event_landing_registry=event_landing_registry,
            )
        register_business_workspace_acquisition_routes(router=router, auth_bundle=auth_bundle)
        if owner_action_draft_projector is not None:
            register_business_workspace_decision_routes(
                router=router,
                auth_bundle=auth_bundle,
                projector=owner_action_draft_projector,
            )
        if process_workspace is not None and process_request_idempotency is not None and headless_handlers is not None:
            register_business_workspace_process_routes(
                router=router, auth_bundle=auth_bundle, workspace=process_workspace, headless_handlers=headless_handlers,
                request_idempotency=process_request_idempotency, enforce_public_security=enforce_public_security,
            )
    register_public_client_outcome_routes(
        router=router,
        client_outcome_handlers=client_outcome_handlers,
        economic_handlers=economic_handlers,
        enforce_public_security=enforce_public_security,
        authenticated_tenant=authenticated_tenant,
        raise_boundary_error=raise_boundary_error,
    )
    if analytics_handlers is not None:
        register_analytics_routes(
            router=router,
            analytics_handlers=analytics_handlers,
            security_guard=security_guard,
            auth_bundle=auth_bundle,
        )


__all__ = [
    'CANON_FASTAPI_PUBLIC_ROUTES_FINAL_OWNER',
    'CANON_PRODUCTION_GUARD_PRINCIPAL_CONTRACT_REQUIRED',
    '_cta_status_response',
    '_cta_submit_response',
    'register_public_api_routes',
]
