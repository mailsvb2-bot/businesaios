from runtime.inference import (
    DistributedInferenceNodeAttestation,
    DistributedInferenceNodeAttestationPolicy,
    DistributedInferenceNodeHealthScoring,
    DistributedInferenceNodeResultConsensus,
)


def test_inference_distributed_owner_exports_are_visible_from_package_root():
    assert DistributedInferenceNodeAttestation is not None
    assert DistributedInferenceNodeAttestationPolicy is not None
    assert DistributedInferenceNodeHealthScoring is not None
    assert DistributedInferenceNodeResultConsensus is not None
