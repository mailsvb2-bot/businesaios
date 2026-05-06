# Release cleaning report

Source archive: `businesaios_canon_merged_best_2026-05-06.zip`

This archive was cleaned without changing source code, tests, deployment descriptors, dependency files, or `.env.example` templates.

Removed as non-release/runtime or secret-like local state:

- `data/security/key_provider.json`
- `data/security/secret_vault.json`
- `data/config/tenant_config_audit.jsonl`
- `data/connectors/connector_health_history.json`
- `data/governance/control_plane_audit.jsonl`
- `data/governance/market_intelligence_operator_store.json`
- `data/observability/market_intelligence_observability_store.json`

Defensive cleanup also removed cache/build/local artifacts if present: `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.cache`, `.hypothesis`, `*.pyc`, `*.pyo`, logs, temp/backup files, local DB files, and real `.env` files.

Preserved examples/seeds/templates:

- `.env.example`
- `env.example`
- `data/plans.json`
- `data/tenancy/tenant_policies.json`
- `data/tenancy/tenant_registry.json`
- source code, tests, docs, Docker, systemd/deploy descriptors, CI workflows.
