from runtime.inference.distributed import (
    DistributedInferenceNodeAttestation,
    DistributedInferenceNodeAttestationPolicy,
    DistributedInferenceNodeHealthScoring,
    DistributedInferenceNodeRegistry,
    DistributedInferenceNodeResultConsensus,
    DistributedInferenceNodeSelectionPolicy,
)


def test_distributed_runtime_root_exports_extended():
    assert DistributedInferenceNodeAttestation(node_id='n1', attested=True, evidence='ok').node_id == 'n1'
    assert DistributedInferenceNodeAttestationPolicy is not None
    assert DistributedInferenceNodeHealthScoring is not None
    assert DistributedInferenceNodeRegistry is not None
    assert DistributedInferenceNodeResultConsensus is not None
    assert DistributedInferenceNodeSelectionPolicy is not None
