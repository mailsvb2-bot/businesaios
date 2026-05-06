from canon.allowed_dependency_graph import ALLOWED_DEPENDENCY_GRAPH


def test_dependency_graph_has_core_edges():
    assert 'core.decision' in ALLOWED_DEPENDENCY_GRAPH
    assert 'execution' in ALLOWED_DEPENDENCY_GRAPH['flow']
