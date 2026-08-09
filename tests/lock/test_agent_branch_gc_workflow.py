from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/prune-stale-branches.yml")
EXPECTED_BOOTSTRAP_BRANCHES = {
    "agent/branch-gc-bootstrap",
    "agent/canonical-commercial-offer-candidates",
    "agent/canonical-messaging-contact-basis",
    "agent/canonical-sales-evidence-foundation",
    "agent/canonical-sales-human-handoff",
    "agent/canonical-sales-integration-final",
    "agent/ci-actions-probe-219",
    "agent/finish-product-onboarding-v2",
    "agent/issue-171-attribution-i001-ratchet",
    "agent/issue-171-config-i001-ratchet",
    "agent/issue-171-config-i001-ratchet-v2",
    "agent/issue-171-contracts-up012-ratchet",
    "agent/issue-171-crm-f401-ratchet",
    "agent/issue-171-demand-gravity-f401-ratchet",
    "agent/issue-171-demand-learning-i001-ratchet",
    "agent/issue-171-demand-seo-i001-ratchet",
    "agent/issue-171-guardrails-f401-ratchet",
    "agent/issue-171-guardrails-f401-ratchet-v2",
    "agent/issue-171-infra-f401-ratchet",
    "agent/issue-171-intent-i001-ratchet",
    "agent/issue-171-kernel-f401-ratchet",
    "agent/issue-171-ports-e402-ratchet",
    "agent/issue-171-presentation-i001-ratchet",
    "agent/issue-171-release-i001-ratchet",
    "agent/issue-171-release-i001-ratchet-v2",
    "agent/issue-171-routing-i001-ratchet",
    "agent/issue-171-routing-i001-ratchet-v2",
    "agent/issue-171-scripts-i001-ratchet",
    "agent/issue-171-shared-f401-ratchet",
    "agent/issue-173-capability-operator-view-consolidation",
    "agent/issue-173-capability-operator-view-consolidation-clean",
    "agent/issue-173-provider-admin-metadata-consolidation",
    "agent/issue-173-provider-admin-test-consolidation",
    "agent/issue-173-provider-admin-wave-consolidation-v2",
    "agent/issue-173-security-runtime-summary-consolidation",
    "agent/issue-236-live-read-telegram-hubspot",
    "agent/issue-236-multichannel-webhook-hardening",
    "agent/issue-236-owner-provider-workspace",
    "agent/issue-236-owner-session-bootstrap",
    "agent/issue-236-owner-workspace-frontend",
    "agent/issue-236-owner-workspace-frontend-clean",
    "agent/issue-236-owner-workspace-integrated",
    "agent/issue-236-provider-connection-status",
    "agent/issue-236-server-owned-onboarding-identity",
    "agent/issue-239-multichannel-provider-parity",
    "agent/issue-241-whatsapp-http-truth-certification",
    "agent/issue-241-whatsapp-http-truth-clean",
    "agent/product-onboarding-integration-marketplace",
    "agent/product-self-service-workspace",
    "agent/tenancy-f401-ratchet",
}


def _bootstrap_branches(text: str) -> list[str]:
    marker = "      BOOTSTRAP_BRANCHES: |\n"
    start = text.index(marker) + len(marker)
    end = text.index("    steps:\n", start)
    return [line.strip() for line in text[start:end].splitlines() if line.strip()]


def test_stale_branch_pruning_uses_one_fail_closed_owner() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert not Path(".github/workflows/agent-branch-gc.yml").exists()
    assert "pull_request_target" not in text
    assert "github.event.pull_request.merged == true" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "startsWith(github.event.pull_request.head.ref, 'agent/')" in text
    assert "EXPECTED_SHA: ${{ github.event.pull_request.head.sha }}" in text
    assert 'current_sha = str(payload["object"]["sha"])' in text
    assert "if current_sha != expected_sha:" in text
    assert "preserved_changed_ref=" in text
    assert "github.event.pull_request.head.ref || github.run_id" in text
    assert "cancel-in-progress: false" in text
    assert text.count("contents: write") == 2
    assert 'request("GET", f"{api_root}/git/ref/{encoded_ref}")' in text
    assert 'request("DELETE", f"{api_root}/git/refs/{encoded_ref}")' in text
    assert "Delete every non-default branch" not in text


def test_stale_branch_bootstrap_pins_complete_audited_allowlist() -> None:
    branches = _bootstrap_branches(WORKFLOW.read_text(encoding="utf-8"))

    assert len(branches) == len(set(branches))
    assert set(branches) == EXPECTED_BOOTSTRAP_BRANCHES
    assert "main" not in branches
