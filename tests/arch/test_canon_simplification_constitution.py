from canon.simplification_constitution import (
    ALL_CANON_INVARIANTS,
    SIMPLIFICATION_RULES,
    SimplificationClass,
    SimplificationIntent,
    SimplificationVerdict,
)
from canon.simplification_contracts import (
    LayerAssessment,
    SimplificationProposal,
    assert_canon_simplification,
    classify_layer_for_simplification,
)


def test_canon_simplification_constitution_is_not_empty() -> None:
    assert ALL_CANON_INVARIANTS
    assert SIMPLIFICATION_RULES


def test_meaningful_domain_layer_cannot_be_deleted() -> None:
    proposal = SimplificationProposal(
        target="core.retention.engine",
        intent=SimplificationIntent.DELETE,
        expected_verdict=SimplificationVerdict.DELETE_AS_DUPLICATE,
        preserves_functionality=True,
        preserves_decision_discipline=True,
        preserves_safety=True,
        preserves_observability=True,
        preserves_domain_boundaries=True,
        regression_tests_added=True,
        assessments=(
            LayerAssessment(
                name="core.retention.engine",
                layer_class=SimplificationClass.DOMAIN_LOGIC,
                has_real_domain_logic=True,
                enforces_safety_invariant=False,
                enforces_decision_discipline=False,
                preserves_observability=False,
                is_public_contract=False,
            ),
        ),
    )

    try:
        assert_canon_simplification(proposal)
    except ValueError as exc:
        assert "cannot_simplify_meaningful_layer:core.retention.engine" in str(exc)
    else:
        raise AssertionError("meaningful domain layer deletion must be rejected")


def test_parasitic_proxy_layer_should_be_merge_candidate() -> None:
    verdict = classify_layer_for_simplification(
        LayerAssessment(
            name="runtime.some_proxy_layer",
            layer_class=SimplificationClass.PROXY_GLUE,
            has_real_domain_logic=False,
            enforces_safety_invariant=False,
            enforces_decision_discipline=False,
            preserves_observability=False,
            is_public_contract=False,
            only_proxies_data=True,
        )
    )
    assert verdict == SimplificationVerdict.MERGE_INTO_NEIGHBOR


def test_public_contract_may_only_stay_as_thin_adapter() -> None:
    verdict = classify_layer_for_simplification(
        LayerAssessment(
            name="runtime.public_read_api",
            layer_class=SimplificationClass.BOUNDARY_ADAPTER,
            has_real_domain_logic=False,
            enforces_safety_invariant=False,
            enforces_decision_discipline=False,
            preserves_observability=False,
            is_public_contract=True,
            only_proxies_data=True,
        )
    )
    assert verdict == SimplificationVerdict.KEEP_AS_THIN_ADAPTER


def test_architectural_lock_blur_is_rejected() -> None:
    proposal = SimplificationProposal(
        target="tests.arch.transition_contracts",
        intent=SimplificationIntent.MERGE,
        expected_verdict=SimplificationVerdict.MERGE_INTO_NEIGHBOR,
        preserves_functionality=True,
        preserves_decision_discipline=True,
        preserves_safety=True,
        preserves_observability=True,
        preserves_domain_boundaries=True,
        regression_tests_added=True,
        preserves_architectural_locks=False,
        preserves_lock_signal_localization=False,
        assessments=(
            LayerAssessment(
                name="tests.arch.test_canonical_path_locks",
                layer_class=SimplificationClass.TEST_LOCK,
                has_real_domain_logic=False,
                enforces_safety_invariant=True,
                enforces_decision_discipline=True,
                preserves_observability=False,
                is_public_contract=False,
            ),
        ),
    )

    try:
        assert_canon_simplification(proposal)
    except ValueError as exc:
        text = str(exc)
        assert "architectural_lock_blur_forbidden" in text
        assert "architectural_lock_signal_localization_required" in text
    else:
        raise AssertionError("architectural lock blur must be rejected")
