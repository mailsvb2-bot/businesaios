from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/prune-stale-branches.yml")
AUDIT = Path(".github/branch-prune-audit.txt")
EXPECTED_AUDIT = {
    "agent/canonical-commercial-offer-candidates": "f2b61b90113c0b5d9b608c6a89d99dfa963dbe8a",
    "agent/canonical-messaging-contact-basis": "8fb8055d91849d01d8f4f6e0e0f25a8a46147508",
    "agent/canonical-sales-evidence-foundation": "a2b7975f8f070b5104d148a4b7d9a00be81a2461",
    "agent/canonical-sales-human-handoff": "e353534256ee6923a4962c327f9c16ec6e1ac38e",
    "agent/canonical-sales-integration-final": "bf9c06a0f17dc6e609d73954df46b05e1ddcbeb4",
    "agent/ci-actions-probe-219": "e0cfdfbcab8e2f3a1d6b0e3bf8b2847f5fcc8520",
    "agent/finish-product-onboarding-v2": "0a61b7cbd68183119226bfd60807fb8e399c0fb2",
    "agent/issue-171-attribution-i001-ratchet": "c8602e5a9c62615d0089bf5ea915c36fd461cc36",
    "agent/issue-171-config-i001-ratchet": "3b1020e1d5840d8562e314c347797e4fe8e566d1",
    "agent/issue-171-config-i001-ratchet-v2": "af7fc0e04852f854207c3d9352027ae0864d925b",
    "agent/issue-171-contracts-up012-ratchet": "5b08488c4fe6ef8f7fed6e5a95e52f2531a34aa4",
    "agent/issue-171-crm-f401-ratchet": "0e789f2d83f18b656ca105071b2adf97abd8511c",
    "agent/issue-171-demand-gravity-f401-ratchet": "170dfb26227d6a6608bde436f127b933317eacbd",
    "agent/issue-171-demand-learning-i001-ratchet": "434cdfafd302b841d9a209f69458cece82b923da",
    "agent/issue-171-demand-seo-i001-ratchet": "045768851775806e04590dd4f8071a42bc15616d",
    "agent/issue-171-guardrails-f401-ratchet": "261143ba36f1fcf5df9e43fd63483c81c05ba9ff",
    "agent/issue-171-guardrails-f401-ratchet-v2": "0b288589f9096b76fb5ae3b8b9434c97a8ca1e80",
    "agent/issue-171-infra-f401-ratchet": "830ad1e2fc59780f97a2808319cd74b1d905486f",
    "agent/issue-171-intent-i001-ratchet": "ac5f1ae0dd569422fa4ecea062492f3b26225e8d",
    "agent/issue-171-kernel-f401-ratchet": "7fbbd270af8420db59afe08d49f206861a65a335",
    "agent/issue-171-ports-e402-ratchet": "f5c7f316dcc5f750198d024270241d4a70a4bdf0",
    "agent/issue-171-presentation-i001-ratchet": "aaed51e0d54bc6a604ab9e956669a0ef91fffc98",
    "agent/issue-171-release-i001-ratchet": "1457a13e82061659fcab7949dc81e01b549a62a5",
    "agent/issue-171-release-i001-ratchet-v2": "d8594f954f775179085448524c996e8aa687d46c",
    "agent/issue-171-routing-i001-ratchet": "ac5f1ae0dd569422fa4ecea062492f3b26225e8d",
    "agent/issue-171-routing-i001-ratchet-v2": "16e7dd1a6ffc6d14e4e522443c85b828fa26d80a",
    "agent/issue-171-scripts-i001-ratchet": "1cd541c00d896834059a38da2c4ecab15360ae80",
    "agent/issue-171-shared-f401-ratchet": "157c6b3893c7295fc2a01ac934c7895ab3fdf62d",
    "agent/issue-173-capability-operator-view-consolidation": "5ff86f2f3358746724afaf2ef9ca1d1ea457fbab",
    "agent/issue-173-capability-operator-view-consolidation-clean": "818f4bfa0259c5aad90fc08e21488ba24a07a80b",
    "agent/issue-173-provider-admin-metadata-consolidation": "72d2769b185945407b8932775f274958785cd34f",
    "agent/issue-173-provider-admin-test-consolidation": "4e5b5df996e935c76539921d31753518530dff8c",
    "agent/issue-173-provider-admin-wave-consolidation-v2": "5c0b98e02307498ac0730faed285d686c095b391",
    "agent/issue-173-security-runtime-summary-consolidation": "de49f3e87eace79832a39b5b3bf5887a60f12c7a",
    "agent/issue-236-live-read-telegram-hubspot": "79d178c5a29c0bd168730aa9c6c4529f869131ac",
    "agent/issue-236-multichannel-webhook-hardening": "0398e159d604b10bdddb8bd4f6d1a5ad9c47459b",
    "agent/issue-236-owner-provider-workspace": "b03ff095cd15de8886730d0f61ea74485897c123",
    "agent/issue-236-owner-session-bootstrap": "8174991678786debef0735c75d98442b0b103aae",
    "agent/issue-236-owner-workspace-frontend": "0981c1919fbd36cd16a06535c60cf6d0e9ca5372",
    "agent/issue-236-owner-workspace-frontend-clean": "c88e17dc888bf43d767f5e7d1afe2bd0dfd6e4ed",
    "agent/issue-236-owner-workspace-integrated": "caa4ee40b62ce610de37fec8ec4cd4188024623f",
    "agent/issue-236-provider-connection-status": "365bbf7b95dab22cafca66baf8e78906ed538fd1",
    "agent/issue-236-server-owned-onboarding-identity": "417959d21b0aa9dd1d2997069fd6920f50ff4906",
    "agent/issue-239-multichannel-provider-parity": "af3cbfcb8d687698584ee940970f80c9a838c201",
    "agent/issue-241-whatsapp-http-truth-certification": "53a37f7ce87d6007bee889d4243961070ef43449",
    "agent/issue-241-whatsapp-http-truth-clean": "c2c8a3ef7240c284889ab76e0a8959faa7c32275",
    "agent/product-onboarding-integration-marketplace": "e406b52ccb212889fb30e00ab9a700c1c6f82c06",
    "agent/product-self-service-workspace": "710ce542c02c1ef4a1b7bf190e755fc50d2110d8",
    "agent/tenancy-f401-ratchet": "aa3198ff72cbc3e7e404efaa56028c00d974503b",
}


def _audit_entries() -> tuple[list[str], dict[str, str]]:
    lines = [line.strip() for line in AUDIT.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries: dict[str, str] = {}
    for line in lines:
        sha, branch = line.split()
        assert branch not in entries
        entries[branch] = sha
    return lines, entries


def test_stale_branch_pruning_uses_one_revision_atomic_owner() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert not Path(".github/workflows/agent-branch-gc.yml").exists()
    assert "pull_request_target" not in text
    assert "concurrency:" not in text
    assert "github.event.pull_request.merged == true" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "startsWith(github.event.pull_request.head.ref, 'agent/')" in text
    assert "EXPECTED_SHA: ${{ github.event.pull_request.head.sha }}" in text
    assert text.count("contents: write") == 2
    assert text.count("persist-credentials: false") == 2
    assert text.count("gh auth setup-git") == 2
    assert text.count('--force-with-lease="$ref:$expected_sha"') == 2
    assert text.count('git ls-remote origin "$ref"') == 2
    assert "branch-prune-audit.txt" in text
    assert "/git/refs/" not in text
    assert "Delete every non-default branch" not in text


def test_stale_branch_audit_pins_every_reviewed_revision() -> None:
    lines, entries = _audit_entries()

    assert len(lines) == 49
    assert entries == EXPECTED_AUDIT
    assert all(branch.startswith("agent/") for branch in entries)
    assert all(len(sha) == 40 and set(sha) <= set("0123456789abcdef") for sha in entries.values())
    assert "main" not in entries
    assert "agent/branch-gc-bootstrap" not in entries
