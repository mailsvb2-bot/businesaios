.PHONY: test test-clean ci-guard regen-manifest runtime-release release perf-top manifest ci-locks locks gen docs canon-audit canon-audit-full

ci-guard:
	./ci/check_prod_strict.sh
	@if [ -f prod.env ]; then ./ci/check_prod_strict.sh prod.env; fi
	@if [ -f .env.prod ]; then ./ci/check_prod_strict.sh .env.prod; fi

ci-locks:
	./ci/check_locks.sh

locks:
	./ci/check_locks.sh

gen:
	python scripts/gen_runtime_actions_docs.py

docs: gen
	@echo "docs generated"

canon-audit:
	python -m tools.canon_audit.cli . --scope operational --json-out .artifacts/reports/canon-operational.json

canon-audit-full:
	python -m tools.canon_audit.cli . --scope full --json-out .artifacts/reports/canon-full.json

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q

# Hermetic clean test run (removes caches/db/locks before executing)
test-clean:
	python scripts/run_tests_clean.py -q

perf-top:
	python -m analytics.latency_top10 --top 10

regen-manifest:
	python tools/regen_release_manifest.py --write

manifest:
	python -m release.tools.rebuild_manifest

runtime-release:
	python scripts/package_release.py

release: ci-guard test regen-manifest runtime-release
	@echo "Release checks passed."

.PHONY: check-world-model-integrity
check-world-model-integrity:
	python scripts/check_world_model_integrity.py

.PHONY: migrate-world-model-canonical
migrate-world-model-canonical:
	python scripts/migrate_world_model_to_canonical.py

.PHONY: test-world-model
test-world-model:
	pytest -q tests/test_world_model_boot_check.py \
	         tests/test_world_model_forbidden_paths.py \
	         tests/test_world_model_self_check.py \
	         tests/test_world_model_pin_guard.py \
	         tests/test_world_model_replay.py \
	         tests/test_world_model_events.py \
	         tests/test_world_model_metadata.py \
	         tests/test_canonical_decision_world_model.py \
	         tests/test_canonical_decision_world_model_metadata.py \
	         tests/test_migrate_world_model_to_canonical.py

.PHONY: ci-world-model
ci-world-model: check-world-model-integrity test-world-model

.PHONY: check-canon-domain-fs
check-canon-domain-fs:
	python scripts/check_canon_domain_file_system.py

.PHONY: ci-bootstrap
ci-bootstrap:
	python scripts/ci/bootstrap.py

.PHONY: ci-doctor
ci-doctor:
	python scripts/ci/cli.py --gate doctor

.PHONY: ci-fast
ci-fast:
	python scripts/ci/cli.py --gate fast

.PHONY: ci-full
ci-full:
	python scripts/ci/cli.py --gate full

.PHONY: ci-release
ci-release:
	python scripts/ci/cli.py --gate release

.PHONY: ci-pre-push
ci-pre-push:
	python scripts/ci/cli.py --gate pre-push

.PHONY: ci-pre-release
ci-pre-release:
	python scripts/ci/cli.py --gate pre-release

.PHONY: ci-install-hooks
ci-install-hooks:
	python scripts/ci/install_hooks.py


.PHONY: test-headless
test-headless:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
		tests/unit/execution/test_retry_taxonomy.py \
		tests/unit/execution/test_policy_explainer.py \
		tests/unit/execution/test_outcome_normalizer.py \
		tests/unit/execution/test_cross_run_comparator.py \
		tests/unit/execution/test_execution_public_api.py \
		tests/integration/test_headless_retry_policy_and_normalized_outcomes.py \
		tests/integration/test_headless_cross_run_compare.py \
		tests/integration/test_business_memory_state_adapter.py \
		tests/integration/test_business_memory_policy_and_compaction.py \
		tests/integration/test_business_memory_corruption_guard.py
