
## Wave 44 compat-cluster collapse

Deleted dead compat leaves from `core/ai/*` after consumer and lock verification:

- `core/ai/decision_envelope_builder.py` -> `application/decision_runtime/envelope_builder.py`
- `core/ai/decision_emission.py` -> `application/decision_runtime/emission.py`
- `core/ai/decision_flow.py` -> `application/decision_runtime/flow.py`
- `core/ai/decision_gate.py` -> `application/decision_runtime/gate.py`
- `core/ai/decision_run.py` -> `application/decision_runtime/run.py`
- `core/ai/decision_signer.py` -> `kernel/decision_signer.py`
- `core/ai/decision_state_constraints.py` -> `application/decision_state/state_constraints.py`
- `core/ai/decision_state_enrichment.py` -> `application/decision_state/state_enrichment.py`
- `core/ai/decision_state_world_model_enricher.py` -> `application/decision_state/state_world_model_enricher.py`

Architecture locks and manifests now treat the final-owner paths as canonical; the removed files are no longer part of the live compat surface.

# CANON Namespace Migration Map v1

This document records the **required migration direction** for legacy namespace
owners. During migration, thin compatibility shims may exist, but ownership must
flow only in the directions listed below.

- `boot` -> `bootstrap`
- `runtime` -> `application`, `adapters`, `entrypoints`, `bootstrap`, `observability`, `security`
- `core` -> `kernel`, `domain`, `application`, `ports`, `observability`, `governance`, `security`
- `interfaces` -> `entrypoints`, `adapters`
- `interfaces/api` -> `entrypoints/api`, `adapters/api/fastapi`
- `headless` -> `application/headless`, `entrypoints`
- `infra` -> `adapters`
- `infrastructure` -> `adapters`

Migration must not create new god modules. A legacy owner may remain only as a
thin compatibility shell with no autonomous business logic.

## Wave 4 owner transfers

- `boot/runtime_boot_guard.py` -> `bootstrap/runtime_boot_guard.py`
- `boot/runtime_boot_manifest.py` -> `bootstrap/runtime_boot_manifest.py`
- `boot/runtime_boot_report.py` -> `bootstrap/runtime_boot_report.py`
- `boot/runtime_dependency_sets.py` -> `bootstrap/runtime_dependency_sets.py`
- `boot/runtime_manifest_support.py` -> `bootstrap/runtime_manifest_support.py`
- `boot/runtime_service_specs.py` -> `bootstrap/runtime_service_specs.py`
- `interfaces/api/headless_route_handlers.py` -> `entrypoints/api/headless_route_handlers.py`
- `interfaces/api/governance_route_handlers.py` -> `entrypoints/api/governance_route_handlers.py`
- `interfaces/api/metrics_route_handlers.py` -> `entrypoints/api/metrics_route_handlers.py`
- `interfaces/api/fastapi_dependencies.py` -> `adapters/api/fastapi/dependencies.py`
- `interfaces/api/fastapi_router_support.py` -> `adapters/api/fastapi/router_support.py`
- `interfaces/api/fastapi_router_public_routes.py` -> `adapters/api/fastapi/public_routes.py`
- `interfaces/api/fastapi_router_control_plane_routes.py` -> `adapters/api/fastapi/control_plane_routes.py`

## Wave 5 owner transfers
- `boot/bootstrap_config_surface.py` -> `bootstrap/bootstrap_config_surface.py`
- `boot/runtime_boot.py` -> `bootstrap/runtime_boot.py`
- `boot/system_registry_boot.py` -> `bootstrap/system_registry_boot.py`
- `boot/system_boot_surface.py` -> `bootstrap/system_boot_surface.py`
- `boot/http_boot_surface.py` -> `bootstrap/http_boot_surface.py`
- `boot/platform_boot_surface.py` -> `bootstrap/platform_boot_surface.py`
- `boot/platform_boot_contract.py` -> `bootstrap/platform_boot_contract.py`
- `interfaces/api/{admin,approval,audit,connector_admin,webhook,queue_ops,baseline,business_memory,drift,governance_advanced}_route_handlers.py` -> `entrypoints/api/*`

## Wave 6 owner transfers

- `runtime/boot/world_model_contract.py` -> `bootstrap/world_model_contract.py`
- `runtime/boot/world_model_builder.py` -> `bootstrap/world_model_builder.py`
- `runtime/boot/world_snapshot_service.py` -> `bootstrap/world_snapshot_service.py`
- `runtime/boot/world_model_boot.py` -> `bootstrap/world_model_boot.py`
- `runtime/boot/system_builder.py` -> `bootstrap/system_builder.py`
- `runtime/boot/system_builder_steps.py` -> `bootstrap/system_builder_steps.py`
- `interfaces/api/action_mapper.py` -> `entrypoints/api/action_mapper.py`
- `interfaces/api/error_mapper.py` -> `entrypoints/api/error_mapper.py`
- `interfaces/api/execute_action_handler.py` -> `entrypoints/api/execute_action_handler.py`
- `interfaces/api/execute_action_port_provider.py` -> `entrypoints/api/execute_action_port_provider.py`
- `interfaces/api/execute_action_stack_bundle.py` -> `entrypoints/api/execute_action_stack_bundle.py`
- `interfaces/api/execute_action_with_guards.py` -> `entrypoints/api/execute_action_with_guards.py`
- `interfaces/api/execute_action_with_control_plane.py` -> `entrypoints/api/execute_action_with_control_plane.py`
- `interfaces/api/api_handler_bundle.py` -> `entrypoints/api/api_handler_bundle.py`

## Wave 8 owner transfers

- `runtime/boot/{failure_policy,governance_boot,governance_execution_boot,human_governance_boot,safety_control_boot,tenant_hard_gate,tenant_self_check,product_boot,product_system_builder,product_system_builder_contracts,product_system_builder_pipeline}` -> `bootstrap/*`
- `interfaces/api/{approval_route_support,queue_ops_route_support,openapi_tags,signature_binding,error_models,baseline_models,business_memory_models,drift_models,governance_advanced_models,queue_ops_models,response_presenter}` -> `entrypoints/api/*`


## Wave 9 owner transfers

- `runtime/boot/ads_apply_provider.py` -> `bootstrap/ads_apply_provider.py`
- `runtime/boot/ads_wiring.py` -> `bootstrap/ads_wiring.py`
- `runtime/boot/ads_write_gateway.py` -> `bootstrap/ads_write_gateway.py`
- `runtime/boot/knowledge_boot.py` -> `bootstrap/knowledge_boot.py`
- `runtime/boot/knowledge_bundle.py` -> `bootstrap/knowledge_bundle.py`
- `runtime/boot/knowledge_event_publisher.py` -> `bootstrap/knowledge_event_publisher.py`
- `runtime/boot/knowledge_wiring.py` -> `bootstrap/knowledge_wiring.py`
- `interfaces/api/execute_action_request_envelope.py` -> `entrypoints/api/execute_action_request_envelope.py`
- `interfaces/api/execute_action_audit_payload.py` -> `entrypoints/api/execute_action_audit_payload.py`
- `interfaces/api/execute_action_idempotency_store.py` -> `entrypoints/api/execute_action_idempotency_store.py`
- `interfaces/api/headless_runtime_provider.py` -> `entrypoints/api/headless_runtime_provider.py`


## Wave 10 owner transfers

- `runtime/boot/{assembly_runtime,boot_helpers,boot_observability,boot_phases,entrypoint_context,finalize_runtime_args,handlers_wiring,health_server,logging_setup,mode_gate,registration_manifest,route_surface,self_check}` -> `bootstrap/*`
- `interfaces/api/{error_presenter,execute_action_api_stack}` -> `entrypoints/api/*`


## Wave 11 owner transfers

- `execution/headless_models.py` -> `application/headless/models.py`
- `execution/headless_goal_mapper.py` -> `application/headless/goal_mapper.py`
- `execution/headless_feedback.py` -> `application/headless/feedback.py`
- `execution/headless_step_builder.py` -> `application/headless/step_builder.py`
- `execution/headless_stop_policy.py` -> `application/headless/stop_policy.py`
- `execution/headless_decision_gateway.py` -> `application/headless/decision_gateway.py`
- `execution/headless_execution_gateway.py` -> `application/headless/execution_gateway.py`
- `execution/headless_closed_loop.py` -> `application/headless/closed_loop.py`
- `execution/headless_contract.py` -> `application/headless/contract.py`

Legacy `execution/headless_*` surfaces remain as thin compat-shims while runtime acquisition still enters through `execution/headless_boot.py`.

## Wave 12 owner transfers

- `execution/autonomy_*` -> `application/autonomy/autonomy_*`
- live consumers moved to `application.autonomy.*` where compatible
- `execution/autonomy_*` retained as thin compat surfaces during transition


## Wave 13 owner transfers

- `execution/effect_evidence.py` -> `application/evidence/effect_evidence.py`
- `execution/evidence_feedback_state.py` -> `application/evidence/evidence_feedback_state.py`
- `execution/evidence_verifier.py` -> `application/evidence/evidence_verifier.py`
- `execution/evidence_persistence.py` -> `application/evidence/evidence_persistence.py`
- `execution/evidence_roundtrip.py` -> `application/evidence/evidence_roundtrip.py`
- `execution/canonical_governance_decision.py` -> `application/governance/canonical_governance_decision.py`
- `execution/canonical_governance_evidence.py` -> `application/governance/canonical_governance_evidence.py`
- `execution/canonical_governance_timeline.py` -> `application/governance/canonical_governance_timeline.py`
- `execution/canonical_scenario_governance.py` -> `application/governance/canonical_scenario_governance.py`
- `execution/governance_service.py` -> `application/governance/governance_service.py`


## Wave 14 owner transfers
- `execution/capability_*` and `execution/action_capability_matrix.py` now transition to `application/capability/*`.
- `execution/economic_recovery_handoff.py` now transitions to `application/recovery/economic_recovery_handoff.py`.
- Hardest-stage bootstrap/core start: `bootstrap/world_model_contract.py` now transitions to `ports/world_model.py`, and `core/contracts/decision_*` now transition to `kernel/decision_*`.


## Wave 18 owner transfers

- `core/application/*` -> `application/decision/*`
- `core/decision/*` compat surfaces continue delegating to the canonical decision-application layer
- `runtime/application/*` keeps package-root compatibility aliases anchored to `core.application.*` while live consumers can adopt `application.decision.*` directly
- `runtime/platform/support/serving/runtime/action_validator.py` remains a compat surface bound to the canonical core-owned validator to avoid split-brain action validation ownership


## Wave 19 owner transfers

- `core/decisioning/candidate_*` -> `application/decisioning/*` and `kernel/decisioning/*`
- `core/decisioning/route_contract.py` -> `kernel/decisioning/route_contract.py`
- `core/decisioning/decision_types.py` -> `kernel/decisioning/decision_types.py`
- `core/decisioning/decision_graph_contract.py` -> `kernel/decisioning/decision_graph.py`
- `core/decisioning/decision_command.py` -> `application/decisioning/decision_command.py`
- `core/decisioning/decision_core_input_bridge.py` -> `application/decisioning/decision_core_input_bridge.py`
- `core/decisioning/decision_output_guard.py` -> `application/decisioning/decision_output_guard.py`

- Wave 20: core/ai decision runtime cluster -> application/decision_runtime/* (envelope_builder, emission, flow, gate, runtime, run); core/ai surfaces retained as compat wrappers.


## Wave 21 owner transfers

- `core/ai/decision_state_constraints.py` -> `application/decision_state/state_constraints.py`
- `core/ai/decision_state_world_model_enricher.py` -> `application/decision_state/state_world_model_enricher.py`
- `core/ai/decision_state_enrichment.py` -> `application/decision_state/state_enrichment.py`
- `core/ai/world_model_metadata.py` -> `application/decision_state/world_model_metadata.py`
- `core/ai/world_model_replay.py` -> `application/decision_state/world_model_replay.py`
- `core/ai/world_model_pinning.py` -> `kernel/world_model_pin.py`


## Wave 22 owner transfers
- `core/ai/decision_policy_stage.py` -> `application/decision_policy/policy_stage.py`
- `core/ai/decision_pricing.py` -> `application/decision_policy/pricing.py`
- `core/ai/decision_safety.py` -> `application/decision_policy/safety.py`
- `core/ai/decision_signer.py` -> `kernel/decision_signer.py`
- `core/ai/decision_crypto.py` -> `kernel/decision_crypto.py`


### Wave 23
- `core/application/*` now operates as a compatibility surface over `application/decision/*` for dispatcher / validator / service / contract / result / ports.
- `application/decision_runtime/*` now uses final-owner internal imports instead of routing through `core.ai.decision_*` compatibility surfaces.
- Safe `WorldStateV1` consumers were rewired from `core.ai.world_state` to `kernel.world_state`.

## Wave 26 owner-transfer notes
- `core/application/__init__.py` now imports final owners from `application.decision.*` while preserving the historical package root.
- `runtime/application/__init__.py` now defaults to `application.decision.*` for live exports; `_ALIAS_MAP` still anchors historical `core.application.*` compat paths.
- `bootstrap/runtime_integration.py` now types against `application.decision.decision_service.DecisionApplicationService`; `boot/runtime_integration.py` retains the historical import marker required by legacy arch-locks.


## Wave 27

- `core/application/__init__.py` now imports action/result/error/presenter surfaces directly from `application.decision.*` so the package root defaults to final owners instead of routing through compat submodules.
- `runtime/application/__init__.py` keeps `_ALIAS_MAP` on `core.application.*` for historical ABI, but live exports remain anchored to `application.decision.*`.
- `boot/runtime_integration.py` remains a legacy monkeypatch-compatible compat surface while `bootstrap/runtime_integration.py` stays the final typed owner.


## Wave 28 owner transfers

- `core/decision/action_errors.py` -> final owner `application.decision.action_errors`
- `core/decision/action_result.py` -> final owner `application.decision.action_result`
- `core/decision/action_result_presenter.py` -> final owner `application.decision.action_result_presenter`
- `core/decision/action_validator.py` -> final owner `application.decision.action_validator`
- `core/decision/application_ports.py` -> final owner `application.decision.ports`
- `core/decision/application_service.py` -> final owner `application.decision.decision_service`
- `core/decision/decision_contract.py` -> final owner `application.decision.decision_contract`

This wave collapses an extra compat hop (`core.decision.* -> core.application.* -> application.decision.*`) into a direct compat hop (`core.decision.* -> application.decision.*`).


## Wave 29

- `core/decision/__init__.py` now resolves its live owner path directly to `application.decision`, while remaining a transition surface.
- `core.decision` public API compatibility now lives alongside the package root owner surface and still resolves symbols from `application.decision`, avoiding the extra hop through `runtime.application`.
- `runtime.application` remains available as a runtime-facing package root and ABI/compat surface, but it is no longer the canonical owner for `core.decision` package-root exports.


## Wave 30

- `core/application/action_validator.py` now resolves directly to `application.decision.action_validator` as a thin compat shim.
- `runtime/platform/support/serving/runtime/action_validator.py` now resolves directly to `application.decision.action_validator` instead of hopping through `core.application.action_validator`.
- `runtime/platform/support/serving/runtime/__init__.py` keeps the legacy alias name, but its live `action_validator` binding now points at the final owner.


## Wave 31
- `runtime/application/__init__.py` now resolves historical runtime submodule aliases directly to `application.decision.*` final owners rather than `core.application.*` intermediates.
- `canon/collapse_readiness.py` now records `runtime.application.*` collapsed surfaces against `application.decision.*` final owners.
- Architecture and unit locks for runtime application canonicalization now treat `application.decision.*` as the canonical direct target while `core.application.*` remains a compat surface.


### Wave 32 - Runtime application contracts consumer collapse
- `runtime/domain_ports.py`, `runtime/read_only_registry.py`, `runtime/capability_access.py`, `runtime/typed_access.py`, and `runtime/service_exports.py` now import directly from `runtime.application.contracts` rather than hopping through the `runtime.application` package root.
- `runtime/bootstrap/runtime_builder.py`, `runtime/bootstrap/startup_validator.py`, `bootstrap/runtime_integration.py`, and `runtime/ceo/__init__.py` now use `runtime.application.contracts` directly for runtime application builders and contract types.
- `runtime.application` remains the public package root, but internal/runtime-owned contract consumers now prefer the single-owner contracts module.


## Wave 33
- `core/world_state/history/*` moved to final owners in `application/world_state/history_*`.
- `runtime/world_state/_surface.py` now imports history service and summary directly from `application.world_state.*`.
- `core/world_state/history/*` remains as compat surfaces only.


## Wave 34
- Removed dead compat-only files under `core/decision/*` that had no remaining code references:
  - `action_dispatcher.py`
  - `action_errors.py`
  - `action_result.py`
  - `action_result_presenter.py`
  - `action_validator.py`
  - `application_ports.py`
  - `application_service.py`
- `core.decision` keeps package-root and public API compatibility via `core/decision/__init__.py`, so these dead leaf modules are no longer needed.


## Wave 35
- Removed dead compat leaves `core/world_state/history/history_sample.py`, `core/world_state/history/history_metrics.py`, and `core/world_state/history/history_summary.py` after verifying there were no remaining live imports to those leaf modules.
- `application/world_state/history_*` remains the final owner path for samples, metrics, and summaries.
- `core/world_state/history/history_service.py` and `core/world_state/history/history_window.py` remain as transitional compat surfaces because they still have live test/runtime consumers.


## Wave 36

- Removed dead compat leaves `core/world_state/history/history_service.py` and `core/world_state/history/history_window.py` after verifying no live non-test consumers remained.
- `tests/e2e/test_world_state_history_path.py` now imports directly from final owners `application.world_state.history_service` and `application.world_state.history_window`.
- `runtime/world_state/_surface.py` already used final owners, so the legacy history package no longer needed leaf compat modules.

## Wave 37 - dead decisioning compat leaf prune

Safely removed dead compat leaves from `core/decisioning/*` after reference audit:

- `core/decisioning/candidate_space.py`
- `core/decisioning/capability_vocabulary.py`
- `core/decisioning/decision_graph_contract.py`
- `core/decisioning/decision_space_invariants.py`
- `core/decisioning/narrowing_guard.py`
- `core/decisioning/decision_types.py`
- `core/decisioning/decision_output_guard.py`

Final owners already serve these surfaces from:

- `application/decisioning/*`
- `kernel/decisioning/*`

`core/decisioning/__init__.py` remains the minimal transition root around route-contract compatibility only.


## Wave 38

- removed dead compat leaves: `core/decisioning/candidate_collection.py`, `core/decisioning/candidate_observations.py`, `core/decisioning/candidate_scores.py`, `core/decisioning/candidate_types.py`
- test imports now resolve directly to final owners: `application/decisioning/*` and `kernel/decisioning/*`
- `core/decisioning/__init__.py` remains the minimal transition root; deleted leaves were no longer referenced by live code


## Wave 39
- Deleted dead compat leaves from `core/application/*`:
  - `action_dispatcher.py`
  - `action_errors.py`
  - `action_result.py`
  - `action_result_presenter.py`
  - `action_validator.py`
  - `ports.py`
  - `decision_contract.py`
- Deleted dead compat leaves from `core/decisioning/*`:
  - `action_boundary_guard.py`
  - `decision_command.py`
  - `decision_core_enrichment_guard.py`
  - `decision_core_input_bridge.py`
  - `route_contract.py`
- Tests now import final owners directly from `application.decision.*`, `application.decisioning.*`, and `kernel.decisioning.*`.
- `core/application/__init__.py`, `core/decisioning/__init__.py`, and package-root/public API surfaces retain transition compatibility where still needed.

## Wave 41 compat-cluster collapse

- Removed dead compat leaves now that live callers and tests point directly to final owners:
  - `core/ai/decision_policy_stage.py` -> removed; final owner `application/decision_policy/policy_stage.py`
  - `core/ai/decision_safety.py` -> removed; final owner `application/decision_policy/safety.py`
  - `core/ai/decision_crypto.py` -> removed; final owner `kernel/decision_crypto.py`
  - `core/ai/world_model_metadata.py` -> removed; final owner `application/decision_state/world_model_metadata.py`
  - `core/ai/world_model_replay.py` -> removed; final owner `application/decision_state/world_model_replay.py`
- Tests and arch-locks were rewired to assert against final owners instead of deleted compat leaves.
- The migration map now treats these `core/ai/*` surfaces as completed removals rather than retained wrappers.


## Wave 42 compat-cluster collapse

- Removed dead compat leaves from `core/decision_input/*`; final owners now live only under `application/decision_input/*`.
- Tests and arch-locks now import `application.decision_input.*` directly instead of `core.decision_input.*`.
- Canon dependency maps now reference `application.decision_input` as the decision-input owner surface.

## Wave 43 compat-cluster collapse

- Removed dead compat leaves from `core/world_state/*`; final owner leaves now live directly under `application/world_state/*`.
- Deleted these dead wrappers after verifying there were no remaining live imports to them:
  - `core/world_state/boundary_rules.py`
  - `core/world_state/creative_state_builder.py`
  - `core/world_state/economics_state_builder.py`
  - `core/world_state/generic_state_builders.py`
  - `core/world_state/market_state_builder.py`
  - `core/world_state/recommendation_packet_builder.py`
  - `core/world_state/reward_state_builder.py`
  - `core/world_state/state_id.py`
  - `core/world_state/user_state_builder.py`
  - `core/world_state/world_state_assembler.py`
- Tests and legacy canon maps now reference `application.world_state.*` directly for these owner surfaces.
- `core/world_state/packet_enrichment.py` remains as a transitional compat surface because runtime still imports it.



## Wave 45 compat-cluster collapse

Removed dead execution compat leaves after confirming there were no live in-repo consumers left on the legacy import paths:

- `execution/autonomy_feedback_step.py` -> `application/autonomy/autonomy_feedback_step.py`
- `execution/autonomy_recovery_semantics.py` -> `application/autonomy/autonomy_recovery_semantics.py`
- `execution/autonomy_stop_policy.py` -> `application/autonomy/autonomy_stop_policy.py`
- `execution/capability_fallback_contract.py` -> `application/capability/capability_fallback_contract.py`
- `execution/capability_replanning.py` -> `application/capability/capability_replanning.py`

This wave intentionally removed only dead compat leaves and did not touch still-referenced execution surfaces.


## Wave 46 compat-cluster collapse

Removed dead execution compat leaves after migrating tests and internal consumers to final owners:

- `execution/canonical_execution_feedback.py` -> `application/effects/canonical_execution_feedback.py`
- `execution/effect_journal.py` -> `application/effects/effect_journal.py`
- `execution/effect_outcome_vocabulary.py` -> `application/effects/effect_outcome_vocabulary.py`
- `execution/effect_verification_bridge.py` -> `application/effects/effect_verification_bridge.py`
- `execution/evidence_roundtrip.py` -> `application/evidence/evidence_roundtrip.py`
- `execution/failure_pattern_detector.py` -> `application/learning/failure_pattern_detector.py`
- `execution/retry_learning_engine.py` -> `application/learning/retry_learning_engine.py`
- `execution/retry_learning_store.py` -> `application/learning/retry_learning_store.py`
- `execution/retry_taxonomy.py` -> `application/learning/retry_taxonomy.py`

Tests and in-repo consumers now point directly at final owners.


## Wave 47 compat-cluster collapse

Removed dead execution compat leaves whose final owners already live under `application/autonomy/*`:

- `execution/autonomy_decision_step.py` -> `application/autonomy/autonomy_decision_step.py`
- `execution/autonomy_execution_step.py` -> `application/autonomy/autonomy_execution_step.py`
- `execution/autonomy_memory_step.py` -> `application/autonomy/autonomy_memory_step.py`
- `execution/autonomy_state_assembly.py` -> `application/autonomy/autonomy_state_assembly.py`
- `execution/autonomy_safety_bundle.py` -> `application/autonomy/autonomy_safety_bundle.py`

Tests and arch-locks now point directly at final owners.


## Wave 48 compat-cluster collapse

Removed the legacy `runtime/bootstrap_pkg/*` compatibility package after internal imports and arch locks were verified to target canonical owners under `runtime/bootstrap/*`.

Final owners:
- `runtime.bootstrap.bootstrap_attestation`
- `runtime.bootstrap.bootstrap_attestation_store`
- `runtime.bootstrap.bootstrap_audit_trail`
- `runtime.bootstrap.bootstrap_contract`
- `runtime.bootstrap.bootstrap_failfast`
- `runtime.bootstrap.bootstrap_lock`
- `runtime.bootstrap.dependency_wiring`
- `runtime.bootstrap.entrypoint_manifest`
- `runtime.bootstrap.environment_loader`
- `runtime.bootstrap.process_bootstrap`
- `runtime.bootstrap.runtime_builder`
- `runtime.bootstrap.runtime_composition_root`
- `runtime.bootstrap.sovereign_bootstrap`
- `runtime.bootstrap.startup_validator`


## Wave 49 compat-cluster collapse

Collapsed per-file web demand compat leaves into package-owned alias modules.

Removed dead leaf wrappers under `app/web/components/demand/*`:
- `business_quality_card.py`
- `lead_delivery_card.py`
- `live_demand_feed.py`
- `market_balance_card.py`
- `revenue_route_card.py`
- `routing_reason_card.py`

Removed dead leaf wrappers under `app/web/pages/demand/*`:
- `_page_rows.py`
- `demand_overview.py`
- `market_health.py`
- `marketplace_settings.py`
- `page_loader.py`
- `revenue_from_demand.py`

Canonical owners remain package-centered:
- `app.web.components.demand` with real implementations in `renderers.py`
- `app.web.pages.demand` with real implementations in `page_loaders.py`

Historical module imports now resolve through centralized package-owned alias modules instead of standalone compat files.


## Wave 50 compat-cluster collapse

- Retired explicit `app/web/**/public_api/__init__.py` compat package directories.
- `app/web`, `app/web/components`, `app/web/pages`, `app/web/components/demand`, and `app/web/pages/demand` now install their `public_api` alias directly from the owner package root via `runtime.public_api_alias.install_public_api_alias`.
- Arch locks now assert direct owner-installed public API aliases instead of physical compat package directories.


## Wave 51 compat-cluster collapse

- Retired physical `runtime/boot/web/public_api_*.py` compat leaf modules.
- `runtime.boot.web` now installs package-owned submodule aliases for: `public_api_bundles`, `public_api_frameworks`, `public_api_graphs`, `public_api_observability`, `public_api_runtime`, `public_api_services`, and `public_api_settings`.
- Historical imports stay valid through owner-root alias installation instead of standalone wrapper files.
- Arch locks now assert owner-installed alias modules rather than physical wrapper leaves.


## Wave 52 compat-cluster collapse

- Removed physical `boot/registrations/catalog.py` compat shell.
- Removed physical `boot/registrations/register_*` leaf wrappers for catalog-backed and singleton registrations.
- Historical `boot.registrations.catalog` and `boot.registrations.register_*` imports now resolve through package-owned alias modules installed by `boot.registrations`.
- Kept real owner modules intact: `boot/registrations/__init__.py`, `boot/registrations/_catalog_owner.py`, `boot/registrations/simple_singletons.py`, `boot/registrations/register_action_executor.py`, `boot/registrations/register_decision_core.py`, `boot/registrations/register_governance.py`.


### Wave 53 compat-cluster collapse

- Retired 14 physical `runtime/*/public_api.py` pseudofiles for package roots that already expose canonical owner aliases through `runtime.package_alias_namespace`.
- Enabled package-root `public_api` alias installation directly in: `runtime.canon`, `runtime.decision_input`, `runtime.evolution`, `runtime.idempotency`, `runtime.ledger`, `runtime.marketing`, `runtime.ml`, `runtime.pricing`, `runtime.recovery_support`, `runtime.revenue`, `runtime.reward`, `runtime.security`, `runtime.time`, and `runtime.ux`.
- Updated internal runtime decision-input consumers to import from the package owner root instead of the retired `runtime.decision_input.public_api` pseudofile.
- Hardened `tests/arch/test_runtime_root_public_api_pseudofiles_retired_wave176.py` to verify the real filesystem path instead of a dotted pseudo-path.

### Wave 54 compat-cluster collapse

- Retired 24 physical `runtime/*/public_api.py` pseudofiles that had already become package-owned aliases.
- Moved `runtime.*.public_api` compatibility into canonical owner package roots via direct `install_public_api_alias(__name__)` or owner-namespace builders with `install_public_api=True`.
- Updated runtime enforcement consumers to import from owner roots instead of `runtime.enforcement.public_api`.
- Updated arch-locks so they assert physical pseudofile retirement while keeping `runtime.<pkg>.public_api` importability.


## Wave 55 compat-cluster collapse
- retired explicit `public_api.py` leaf shims for `acquisition`, `crm`, `observability`, `observability.platform`, and `observability.platform.observability`
- installed package-owned `public_api` aliases in the owner roots via `canon.public_api_alias.install_public_api_alias(__name__)`
- preserved historical imports while reducing physical package dust


## Wave 56 compat-cluster collapse

- Retired the last physical package-root `public_api.py` compat shells in `boot`, `execution`, and `core.decision`.
- Installed `public_api` aliases directly from `boot/__init__.py`, `execution/__init__.py`, and `core/decision/__init__.py` via `canon.public_api_alias.install_public_api_alias(__name__)`.
- Preserved historical imports (`boot.public_api`, `execution.public_api`, `core.decision.public_api`) while removing the final three physical wrapper files in this cluster.


## Wave 57 compat-cluster collapse
- `runtime/boot/*` compatibility shims collapsed into package-owned alias modules in `runtime/boot/__init__.py`.
- `interfaces/api/*` compatibility shims collapsed into package-owned alias modules in `interfaces/api/__init__.py`.
- Historical imports remain supported without per-file compat leaves.


## Wave 58 compat-cluster collapse

- Retired 19 physical `boot/*` support shims and moved them into package-owned alias modules installed by `boot/__init__.py`.
- Preserved historical imports such as `boot.app_boot_surface`, `boot.runtime_boot`, and `boot.system_registry_boot` without keeping separate compat files on disk.
- Retired 6 top-level `runtime/*` compat leaves (`bootstrap_process`, `bootstrap_prod_guards`, `executor_effects`, `executor_infra`, `executor_ports`, `llm_provider_factory`) and moved them into package-owned alias modules installed by `runtime/__init__.py`.
- Kept `boot/runtime_integration.py` and `runtime/executor_runtime_support.py` intact because they still carry legacy monkeypatch or executable compatibility semantics.


## Wave 59 structural sweep

- Removed 12 physical `core/decision/*` compat leaf modules and moved their historical import paths into package-owned aliases under `core.decision`.
- Removed 2 physical `core/survival/*` compat leaves and retained the historical `core.survival.controller` / `core.survival.metrics` paths via package-owned aliases in `core/survival/__init__.py`.
- Updated arch-lock tests to assert alias resolution instead of requiring file-based compat leaves.

## Wave 60 compat-cluster collapse

Retired residual file-level compat leaves and kept the import paths alive through package-owned alias modules:

- `core/ai/decision_pricing.py` -> `application/decision_policy/pricing.py`
- `core/ai/world_model_pinning.py` -> `kernel/world_model_pin.py`
- `core/ai/world_state.py` -> `kernel/world_state.py`
- `core/creative_intelligence/portfolio_ranker.py` -> `core/scorers/portfolio.py`
- `core/growth/spend_ledger_eventstore.py` -> `core/growth/spend_ledger_event_store.py`
- `core/learning/variant_selector.py` -> `core/scorers/variants.py`
- `core/pricing/rl/selector.py` -> `core/scorers/pricing.py`
- `core/ads/apply/engine.py` -> `core/ads/apply_engine.py`

Tests and lock-files were updated to validate alias-resolution semantics instead of physical shim files.


## Wave 61 compat-cluster collapse

- Retired `core/offers/offer_engine.py`; legacy import now resolves via `core.offers` package alias to `core.offers.engine`.
- Retired `core/products/product_contract.py` and `core/contracts/product_contract.py`; legacy imports now resolve via package aliases to `contracts.product_contract`.
- Retired `runtime/platform/config/yaml_loader.py`; legacy import now resolves via `runtime.platform.config` package alias to `config.yaml_loader_shared`.
