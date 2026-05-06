from __future__ import annotations

"""Canonical runtime package alias namespace for runtime.behavior public API."""

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'BehaviorGraphStore': ('core.ports.behavior_graph_store', 'BehaviorGraphStore'),
    'CohortAggregate': ('core.behavior.cohorts.cohort_aggregate', 'CohortAggregate'),
    'build_behavior_graph_from_events': ('core.behavior_graph', 'build_behavior_graph_from_events'),
    'segment_direction_score': ('core.behavior.cohorts.segment_direction', 'segment_direction_score'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
