from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ("os.getenv(", "os.environ.get(")

TARGETS = [
    "runtime/wiring.py",
    "runtime/boot/builders/marketing_llm.py",
    "bootstrap/ads_wiring.py",
    "runtime/boot/builders/ads_apply_engine.py",
    "runtime/boot/builders/campaign_builder.py",
    "runtime/boot/builders/product_preflight.py",
    "runtime/boot/builders/ads_stack.py",
    "runtime/boot/builders/ads_rl.py",
    "bootstrap/assembly_runtime.py",
    "runtime/boot/telegram_runner.py",
    "bootstrap/boot_phases.py",
    "products/product_loader.py",
    "governance/economic_layer_env.py",
    "interfaces/telegram/runner_helpers.py",
    "interfaces/telegram/read_models/admin_access.py",
    "runtime/_internal/effects_clients/yookassa_client.py",
    "runtime/_internal/effects_clients/telegram_client.py",
    "runtime/_internal/effects_clients/yookassa_webhook_server.py",
    "runtime/_internal/effects_actions/llm_actions.py",
    "runtime/_internal/effects_actions/telegram/startup.py",
    "runtime/_internal/effects_actions/telegram_actions_polling.py",
    "core/events/log.py",
    "core/events/log_emit.py",
    "runtime/governance/pricing_versioning.py",
    "core/offers/catalog_registry.py",
    "core/marketing/evolution.py",
    "runtime/_internal/effects_domains/admin_pricing.py",
    "interfaces/telegram/pipeline/update_processor.py",
    "runtime/guard.py",
    "runtime/bootstrap.py",
    "runtime/guard_protocols.py",
    "runtime/boot/storage_self_check.py",
    "runtime/boot/phase_policy_registry.py",
    "bootstrap/world_model_builder.py",
    "runtime/firewall/singleton_lock.py",
    "runtime/_internal/llm_transport.py",
    "interfaces/telegram/runtime_loops/offer_outcome.py",
    "runtime/platform/outbox/sqlite_pragmas.py",
    "runtime/platform/outbox/sqlite_evolution_outbox.py",
    "infra/secret_provider.py",
    "core/reward/delayed.py",
    "core/retention/engine.py",
    "core/observability/perf_watchdog.py",
    "core/flags/provider.py",
    "core/ai_ceo/safety.py",
    "core/retention/sandbox.py",
    "core/retention/telemetry.py",
    "bootstrap/mode_gate.py",
    "runtime/governance/auto_deploy_guard.py",
    "runtime/security/signing.py",
    "runtime/platform/app_paths.py",
    "runtime/platform/delivery_state.py",
    "scripts/run_tests_clean.py",
    "products/product_resolver.py",
]

def test_selected_modules_do_not_regrow_raw_env_access() -> None:
    for rel in TARGETS:
        path = PROJECT_ROOT / rel
        assert path.exists(), rel
        text = path.read_text(encoding="utf-8")
        assert all(token not in text for token in FORBIDDEN), rel

def test_event_log_legacy_marker_still_present() -> None:
    text = (PROJECT_ROOT / "core/events/log.py").read_text(encoding="utf-8")
    assert "_legacy_event_path" in text
    assert "legacy emit path used" in text

def test_env_csv_helper_still_exists() -> None:
    text = (PROJECT_ROOT / "runtime/platform/config/env_flags.py").read_text(encoding="utf-8")
    assert "def env_csv(" in text
