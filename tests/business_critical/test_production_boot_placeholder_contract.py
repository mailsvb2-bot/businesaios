from __future__ import annotations

from runtime.production_boot_contract import ProductionBootProbe, evaluate_production_boot


def test_production_boot_blocks_placeholder_prod_env_values() -> None:
    report = evaluate_production_boot(
        ProductionBootProbe.from_env(
            {
                "ENV": "prod",
                "APP_PROFILE": "api",
                "DATABASE_URL": "REPLACE_WITH_POSTGRES_DSN",
                "METRO_DB_ENGINE": "postgres",
                "TELEGRAM_BOT_TOKEN": "REPLACE_WITH_TELEGRAM_BOT_TOKEN",
                "TELEGRAM_WEBHOOK_SECRET": "REPLACE_WITH_HIGH_ENTROPY_SECRET",
                "CONTROL_PLANE_API_KEY": "REPLACE_WITH_HIGH_ENTROPY_CONTROL_PLANE_KEY",
                "BUSINESAIOS_SECRET_VAULT_BACKEND": "REPLACE_WITH_PROD_SECRET_BACKEND",
                "BUSINESAIOS_KEY_PROVIDER_BACKEND": "REPLACE_WITH_PROD_KEY_PROVIDER",
                "BAIOS_REQUIRE_QUALITY_TOOLS": "release",
            }
        )
    )

    assert report["status"] == "blocked"
    assert "production_database_url_placeholder_forbidden" in report["violations"]
    assert "production_telegram_token_placeholder_forbidden" in report["violations"]
    assert "production_webhook_secret_placeholder_forbidden" in report["violations"]
    assert "production_control_plane_key_placeholder_forbidden" in report["violations"]
    assert "production_secret_backend_placeholder_forbidden" in report["violations"]
    assert "production_key_provider_placeholder_forbidden" in report["violations"]
    assert report["claims_production_ready"] is False


def test_production_boot_blocks_sqlite_secret_backends_in_prod() -> None:
    report = evaluate_production_boot(
        ProductionBootProbe.from_env(
            {
                "ENV": "prod",
                "APP_PROFILE": "api",
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/businesaios",
                "METRO_DB_ENGINE": "postgres",
                "TELEGRAM_BOT_TOKEN": "123456:real-looking-token",
                "TELEGRAM_WEBHOOK_SECRET": "real-high-entropy-secret",
                "CONTROL_PLANE_API_KEY": "real-control-plane-secret",
                "BUSINESAIOS_SECRET_VAULT_BACKEND": "sqlite",
                "BUSINESAIOS_KEY_PROVIDER_BACKEND": "sqlite",
                "BAIOS_REQUIRE_QUALITY_TOOLS": "release",
            }
        )
    )

    assert report["status"] == "blocked"
    assert "production_sqlite_secret_backend_forbidden" in report["violations"]
    assert "production_sqlite_key_provider_forbidden" in report["violations"]
    assert report["claims_production_ready"] is False
