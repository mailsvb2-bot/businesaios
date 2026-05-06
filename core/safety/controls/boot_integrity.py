from __future__ import annotations

from dataclasses import dataclass, field

from .policy_manifest import PolicyManifestSigner
from .policy_trust_chain import PolicyTrustChain
from .simulation_gate.evidence import SimulationEvidenceVerifier

CANON_SAFETY_BOOT_INTEGRITY = True


@dataclass(frozen=True)
class SafetyBootIntegrityReport:
    healthy: bool
    failures: tuple[str, ...] = field(default_factory=tuple)


class SafetyBootIntegrityChecker:
    def verify(
        self,
        *,
        manifest_signer: PolicyManifestSigner,
        trust_chain: PolicyTrustChain,
        strict: bool = False,
    ) -> SafetyBootIntegrityReport:
        failures: list[str] = []
        if strict and manifest_signer.using_insecure_fallback:
            failures.append('unsafe_policy_signing_key_fallback')
        if strict:
            try:
                manifest_signer._keys.assert_secure_current()  # noqa: SLF001
            except Exception as exc:
                failures.append(str(exc))
        if strict and manifest_signer._keys.has_insecure_fallback_enabled():  # noqa: SLF001
            failures.append('unsafe_policy_signing_fallback_enabled')
        if strict and SimulationEvidenceVerifier().using_insecure_fallback:
            failures.append('unsafe_simulation_evidence_signing_fallback')
        if not trust_chain.verify_all():
            failures.append('policy_trust_chain_invalid')
        return SafetyBootIntegrityReport(healthy=not failures, failures=tuple(failures))


__all__ = ['CANON_SAFETY_BOOT_INTEGRITY', 'SafetyBootIntegrityChecker', 'SafetyBootIntegrityReport']
