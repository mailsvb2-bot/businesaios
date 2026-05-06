import execution as api
import execution.public_api as compat_api


def test_execution_package_root_exposes_headless_contract_surface() -> None:
    assert api.CANON_EXECUTION_PUBLIC_API is True
    assert api.CANON_EXECUTION_PACKAGE_OWNER is True
    assert api.GoalExecutionRequest is compat_api.GoalExecutionRequest
    assert api.GoalExecutionReport is compat_api.GoalExecutionReport
    assert api.HeadlessExecutionContract is compat_api.HeadlessExecutionContract
    assert api.HeadlessRuntime is compat_api.HeadlessRuntime
    assert api.build_headless_runtime is compat_api.build_headless_runtime


def test_execution_package_root_exposes_business_memory_and_governance_extensions() -> None:
    assert api.BusinessMemoryCompactor is compat_api.BusinessMemoryCompactor
    assert api.BusinessMemoryPolicy is compat_api.BusinessMemoryPolicy
    assert api.BusinessOperatingMemory is compat_api.BusinessOperatingMemory
    assert api.GovernanceService is compat_api.GovernanceService
    assert api.MemoryAwareRollbackRecommender is compat_api.MemoryAwareRollbackRecommender


def test_execution_package_root_exposes_business_memory_governance_promotions() -> None:
    assert api.BusinessMemoryGovernanceGate is compat_api.BusinessMemoryGovernanceGate
    assert api.BusinessMemoryPromotionHelper is compat_api.BusinessMemoryPromotionHelper
    assert api.canonical_governance_decision is compat_api.canonical_governance_decision
    assert api.canonical_governance_evidence is compat_api.canonical_governance_evidence


def test_execution_package_root_exposes_business_memory_taxonomy_and_matcher() -> None:
    assert api.BusinessMemoryMatcher is compat_api.BusinessMemoryMatcher
    assert api.BusinessMemoryTaxonomy is compat_api.BusinessMemoryTaxonomy
    assert api.BusinessMemoryQueryService is compat_api.BusinessMemoryQueryService
    assert api.BusinessMemoryStateAdapter is compat_api.BusinessMemoryStateAdapter
