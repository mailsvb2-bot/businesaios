"""Canonical CI Makefile block for bundle apply."""

CI_MAKEFILE_BLOCK = """
.PHONY: ci-bootstrap
ci-bootstrap:
\tpython scripts/ci/bootstrap.py

.PHONY: ci-doctor
ci-doctor:
\tpython scripts/ci/cli.py --gate doctor

.PHONY: ci-fast
ci-fast:
\tpython scripts/ci/cli.py --gate fast

.PHONY: ci-full
ci-full:
\tpython scripts/ci/cli.py --gate full

.PHONY: ci-release
ci-release:
\tpython scripts/ci/cli.py --gate release

.PHONY: ci-pre-push
ci-pre-push:
\tpython scripts/ci/cli.py --gate pre-push

.PHONY: ci-pre-release
ci-pre-release:
\tpython scripts/ci/cli.py --gate pre-release

.PHONY: ci-install-hooks
ci-install-hooks:
\tpython scripts/ci/install_hooks.py
"""
