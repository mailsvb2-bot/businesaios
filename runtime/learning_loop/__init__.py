"""Canonical runtime package alias namespace for runtime.learning_loop public API."""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'LearningBatch': ('core.learning_loop.types', 'LearningBatch'),
    'LearningLoopService': ('core.learning_loop.service', 'LearningLoopService'),
    'PolicyUpdateProposal': ('core.learning_loop.contracts', 'PolicyUpdateProposal'),
    'build_policy_update_proposal': ('core.learning_loop.service', 'build_policy_update_proposal'),
    'explain_policy_update': ('core.learning_loop.explainers.policy_update_explainer', 'explain_policy_update'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
