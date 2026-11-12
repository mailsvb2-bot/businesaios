"""Canonical CI Makefile block for bundle apply."""

CI_MAKEFILE_BLOCK = """
.PHONY: ci-bootstrap
ci-bootstrap:
\tpython scripts/ci/bootstrap.py

.PHONY: ci-doctor
ci-doctor:
\tpython -m scripts.ci.cli --gate doctor

.PHONY: ci-fast
ci-fast:
\tpython -m scripts.ci.cli --gate fast

.PHONY: ci-full
ci-full:
\tpython -m scripts.ci.cli --gate full

.PHONY: ci-release
ci-release:
\tpython -m scripts.ci.cli --gate release

.PHONY: ci-pre-push
ci-pre-push:
\tpython -m scripts.ci.cli --gate pre-push

.PHONY: ci-pre-release
ci-pre-release:
\tpython -m scripts.ci.cli --gate pre-release

.PHONY: ci-install-hooks
ci-install-hooks:
\tpython scripts/ci/install_hooks.py
"""
