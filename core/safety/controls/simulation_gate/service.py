from __future__ import annotations

from ..action_catalog import ActionSafetyCatalog, build_default_action_catalog
from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .evidence import SimulationEvidenceVerifier
from .models import SimulationGatePolicy


class SimulationGate:
    control_name = "simulation_gate"

    def __init__(
        self,
        policy: SimulationGatePolicy,
        catalog: ActionSafetyCatalog | None = None,
        evidence_verifier: SimulationEvidenceVerifier | None = None,
    ):
        self._policy = policy
        self._catalog = catalog or build_default_action_catalog()
        self._evidence_verifier = evidence_verifier or SimulationEvidenceVerifier()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        payload = dict(ctx.payload)
        spec = self._catalog.resolve(ctx.action)
        required_by_prefix = bool(self._policy.required_for_prefixes) and any(str(ctx.action).startswith(prefix) for prefix in self._policy.required_for_prefixes)
        required_explicitly = bool(payload.get("requires_simulation_gate") or payload.get("simulation_required"))
        required_by_catalog = bool(getattr(spec, "simulation_required", False))
        if not required_by_prefix and not required_explicitly and not required_by_catalog:
            return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason="simulation_not_required")
        evidence = self._evidence_verifier.from_payload(ctx)
        verification_fields_present = any(key in payload for key in ('simulation_verified', 'simulation_provenance', 'simulation_signature'))
        signed_artifact_ready = bool(evidence.artifact_fingerprint)
        if evidence.score >= self._policy.min_score and evidence.verified and evidence.provenance and signed_artifact_ready:
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.ALLOW,
                reason="simulation_gate_passed",
                details={
                    "simulation_score": evidence.score,
                    "simulation_provenance": evidence.provenance,
                    "simulation_verified": evidence.verified,
                    "simulation_artifact_fingerprint": evidence.artifact_fingerprint,
                    "simulation_model_fingerprint": evidence.model_fingerprint,
                    "simulation_expires_at": evidence.expires_at,
                },
            )

        strict_artifact_fields_present = any(key in payload for key in ('simulation_signature', 'simulation_artifact_fingerprint', 'simulation_model_fingerprint', 'simulation_expires_at'))
        legacy_compat = (
            not strict_artifact_fields_present
            and float(payload.get('simulation_score', -1.0) or -1.0) >= self._policy.min_score
            and (
                (not verification_fields_present)
                or (bool(payload.get('simulation_verified')) and bool(str(payload.get('simulation_provenance') or '').strip()))
            )
        )
        if legacy_compat:
            return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason="simulation_gate_passed_legacy")
        return ControlDecision(
            control=self.control_name,
            status=ControlStatus.BLOCK,
            reason="simulation_gate_blocked",
            details={
                "simulation_score": evidence.score,
                "required": self._policy.min_score,
                "simulation_verified": evidence.verified,
                "simulation_provenance": evidence.provenance,
                "signature_present": bool(evidence.signature),
                "simulation_artifact_fingerprint": evidence.artifact_fingerprint,
                "simulation_model_fingerprint": evidence.model_fingerprint,
                "simulation_expires_at": evidence.expires_at,
            },
        )
