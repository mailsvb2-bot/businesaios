from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import List

from canon.authority_registry import CANONICAL_AUTHORITY_OWNERS
from canon.sealed_effect_policy import FORBIDDEN_EXTERNAL_EFFECT_LIBRARIES, SEALED_EFFECT_PREFIXES
from tools.canon_audit.ast_semantics import scan_hidden_semantic_numeric_heuristics
from tools.canon_audit.call_graph import build_call_graph
from tools.canon_audit.constructor_flow import build_constructor_flow
from tools.canon_audit.contracts import ArchitectureReport, ArchitectureViolation
from tools.canon_audit.di_container_scan import scan_di_container_antipatterns
from tools.canon_audit.effect_seal_scan import scan_effect_literals_outside_seal
from tools.canon_audit.entrypoint_shortcut_scan import scan_entrypoint_runtime_shortcuts
from tools.canon_audit.factory_resolution import scan_factory_resolution_risks
from tools.canon_audit.formal_owner_lock import validate_formal_owner_lock
from tools.canon_audit.formula_semantics_scan import scan_formula_semantics_outside_policy
from tools.canon_audit.hard_gates import evaluate_hard_gates
from tools.canon_audit.import_graph import (
    PROJECT_ROOT_PREFIXES,
    ImportEdge,
    build_import_graph,
    detect_cycles,
    internal_import_edges,
)
from tools.canon_audit.noop_detector import scan_noop_functions
from tools.canon_audit.owner_graph import detect_export_name_collisions
from tools.canon_audit.owner_misuse_scan import scan_owner_misuse
from tools.canon_audit.package_surface_scan import scan_package_root_surfaces
from tools.canon_audit.path_lock import scan_path_lock_bypasses
from tools.canon_audit.policy_diff_scan import scan_policy_duplication_and_leakage
from tools.canon_audit.provider_wiring_audit import scan_provider_wiring
from tools.canon_audit.registry import ManifestRegistry
from tools.canon_audit.route_resolver import scan_route_expectations
from tools.canon_audit.scanners import scan_dynamic_export_magic, scan_god_modules
from tools.canon_audit.score import CanonSubscores, compute_admission_score_100, compute_raw_score_100
from tools.canon_audit.trace_contract_scan import scan_trace_contracts

REQUIRED_ARCHITECTURE_SCORE = 100.0
ALLOW_COMPAT = False
OPERATIONAL_CANON_INCLUDE_PATHS: tuple[str, ...] = (
    "canon",
    "tools/canon_audit",
    "scripts/ci",
    "tests/canon_audit",
)
FULL_CANON_INCLUDE_PATHS: tuple[str, ...] | None = None


def _startswith_any(value: str, prefixes: Sequence[str]) -> bool:
    return any(value == prefix or value.startswith(prefix + ".") for prefix in prefixes)


def _is_internal_import(target: str) -> bool:
    return _startswith_any(target, PROJECT_ROOT_PREFIXES)


def check_no_compat(registry: ManifestRegistry) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for manifest in registry.all():
        if manifest.is_compat and not ALLOW_COMPAT:
            violations.append(ArchitectureViolation("CANON_NO_COMPAT", "Compat modules are forbidden by the hard Canon.", manifest.module_name))
    return violations


def check_single_authority_owner(registry: ManifestRegistry) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    authority_index = registry.authority_index()
    for authority_name, expected_owner in CANONICAL_AUTHORITY_OWNERS.items():
        owners = authority_index.get(authority_name.value, set())
        if owners != {expected_owner}:
            violations.append(ArchitectureViolation("CANON_SINGLE_AUTHORITY", f"Authority '{authority_name.value}' must belong only to '{expected_owner}', got {sorted(owners)}", authority_name.value))
    return violations


def check_single_public_owner(registry: ManifestRegistry) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for canonical_key, refs in sorted(registry.public_symbol_index().items()):
        if len(refs) > 1:
            violations.append(ArchitectureViolation("CANON_SINGLE_OWNER", f"Canonical public export '{canonical_key}' has multiple owners: {[r.fqname for r in refs]}", canonical_key))
    return violations


def check_manifest_import_rules(registry: ManifestRegistry, import_edges: Iterable[ImportEdge]) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    manifests = {m.module_name: m for m in registry.all()}
    for edge in import_edges:
        manifest = manifests.get(edge.source)
        if manifest is None or not _is_internal_import(edge.target):
            continue
        if manifest.allowed_internal_import_prefixes and not _startswith_any(edge.target, tuple(manifest.allowed_internal_import_prefixes)):
            violations.append(ArchitectureViolation("CANON_IMPORT_ALLOWED", f"Module '{edge.source}' imports internal target '{edge.target}' outside allowed internal import prefixes.", edge.source))
        if manifest.forbidden_internal_import_prefixes and _startswith_any(edge.target, tuple(manifest.forbidden_internal_import_prefixes)):
            violations.append(ArchitectureViolation("CANON_IMPORT_FORBIDDEN", f"Module '{edge.source}' imports forbidden internal target '{edge.target}'.", edge.source))
    return violations


def check_sealed_effects(import_edges: Iterable[ImportEdge]) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for edge in import_edges:
        root_name = edge.target.split(".")[0]
        if root_name in FORBIDDEN_EXTERNAL_EFFECT_LIBRARIES:
            if not _startswith_any(edge.source, SEALED_EFFECT_PREFIXES):
                violations.append(ArchitectureViolation("CANON_SEALED_EFFECTS", f"External effect library '{edge.target}' imported outside sealed zone by '{edge.source}'.", edge.source))
    return violations


def check_import_cycles(import_edges: Iterable[ImportEdge]) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for cycle in detect_cycles(internal_import_edges(import_edges)):
        if len(cycle) > 2:
            violations.append(ArchitectureViolation("CANON_IMPORT_CYCLE", f"Internal import cycle detected: {' -> '.join(cycle)}", cycle[0]))
    return violations


def _build_subscores(registry: ManifestRegistry, violations: Sequence[ArchitectureViolation]) -> CanonSubscores:
    codes = [v.code for v in violations]
    compat_count = sum(1 for m in registry.all() if m.is_compat)
    duplicate_authority_count = sum(max(0, len(owners) - 1) for owners in registry.authority_index().values())
    public_dup_count = sum(max(0, len(refs) - 1) for refs in registry.public_symbol_index().values())

    hidden_logic_count = sum(codes.count(code) for code in ("CANON_HIDDEN_NUMERIC_HEURISTIC", "CANON_POLICY_LEAKAGE", "CANON_POLICY_DUPLICATION", "CANON_FORMULA_OUTSIDE_POLICY"))
    god_count = sum(codes.count(code) for code in ("CANON_GOD_MODULE", "CANON_GOD_PACKAGE_SURFACE"))
    alt_count = sum(codes.count(code) for code in (
        "CANON_PATH_LOCK_BYPASS",
        "CANON_PATH_LOCK_BYPASS_CALL",
        "CANON_ROUTE_FORBIDDEN_CALL",
        "CANON_ENTRYPOINT_RUNTIME_SHORTCUT",
        "CANON_PROVIDER_WIRING_DECISION_RUNTIME",
        "CANON_PROVIDER_WIRING_ENTRYPOINT_EFFECT",
        "CANON_PROVIDER_WIRING_EFFECT_DECISION",
    ))
    fragility_count = sum(codes.count(code) for code in ("CANON_IMPORT_CYCLE", "CANON_DYNAMIC_EXPORT_MAGIC", "CANON_AST_EXPORT_COLLISION", "CANON_FACTORY_RESOLUTION_RISK", "CANON_DI_CONTAINER"))

    return CanonSubscores(
        functional_preservation=1.0 if hidden_logic_count == 0 else 0.40,
        ownership_uniqueness=1.0 if public_dup_count == 0 else 0.0,
        canonical_path_integrity=1.0 if alt_count == 0 else 0.20,
        governance_integrity=1.0 if "CANON_SINGLE_AUTHORITY" not in codes else 0.35,
        evidence_integrity=1.0 if "CANON_OWNER_MISUSE_EVIDENCE" not in codes else 0.35,
        runtime_discipline=1.0 if "CANON_SEALED_EFFECTS" not in codes else 0.0,
        proof_strength=1.0 if "CANON_NOOP_FUNCTION" not in codes else 0.50,
        duplicate_authority_penalty=min(1.0, duplicate_authority_count / 3.0),
        hidden_logic_penalty=min(1.0, hidden_logic_count / 10.0),
        compatibility_penalty=0.0 if compat_count == 0 else 1.0,
        god_module_penalty=min(1.0, god_count / 20.0),
        alternative_route_penalty=min(1.0, alt_count / 10.0),
        fragility_penalty=min(1.0, fragility_count / 20.0),
    )




META_SAFE_PREFIXES = ("canon", "tools.canon_audit", "scripts.ci", "tests.canon_audit")


def _is_meta_safe_subject(subject: str) -> bool:
    return any(subject == prefix or subject.startswith(prefix + ".") for prefix in META_SAFE_PREFIXES)


def _filter_operational_false_positives(violations: Sequence[ArchitectureViolation]) -> list[ArchitectureViolation]:
    filtered: list[ArchitectureViolation] = []
    for violation in violations:
        if violation.code == "CANON_AST_EXPORT_COLLISION":
            continue
        if violation.code in {
            "CANON_DYNAMIC_EXPORT_MAGIC",
            "CANON_HIDDEN_NUMERIC_HEURISTIC",
            "CANON_POLICY_LEAKAGE",
            "CANON_EFFECT_LITERAL_OUTSIDE_SEAL",
            "CANON_GOD_PACKAGE_SURFACE",
            "CANON_FACTORY_RESOLUTION_RISK",
            "CANON_DI_CONTAINER",
            "CANON_TRACE_CONTRACT_WEAK",
        } and _is_meta_safe_subject(violation.subject):
            continue
        filtered.append(violation)
    return filtered

def _dedupe_violations(violations: Sequence[ArchitectureViolation]) -> list[ArchitectureViolation]:
    deduped: list[ArchitectureViolation] = []
    seen = set()
    for violation in violations:
        key = (violation.code, violation.subject, violation.message)
        if key not in seen:
            seen.add(key)
            deduped.append(violation)
    return deduped


def run_canon_checks(project_root: Path, registry: ManifestRegistry | None = None, include_paths: Sequence[str] | None = FULL_CANON_INCLUDE_PATHS) -> ArchitectureReport:
    registry = registry or ManifestRegistry.from_default_manifests()
    import_edges = build_import_graph(project_root, include_paths=include_paths)
    call_edges = build_call_graph(project_root, include_paths=include_paths)
    constructor_edges = build_constructor_flow(project_root, include_paths=include_paths)

    violations: list[ArchitectureViolation] = []
    violations.extend(check_no_compat(registry))
    violations.extend(check_single_authority_owner(registry))
    violations.extend(check_single_public_owner(registry))
    violations.extend(validate_formal_owner_lock(registry))
    violations.extend(check_manifest_import_rules(registry, import_edges))
    violations.extend(check_sealed_effects(import_edges))
    violations.extend(check_import_cycles(import_edges))
    violations.extend(scan_dynamic_export_magic(project_root, include_paths=include_paths))
    violations.extend(scan_hidden_semantic_numeric_heuristics(project_root, include_paths=include_paths))
    violations.extend(scan_god_modules(project_root, include_paths=include_paths))
    violations.extend(scan_path_lock_bypasses(project_root, include_paths=include_paths))
    violations.extend(scan_effect_literals_outside_seal(project_root, include_paths=include_paths))
    violations.extend(scan_noop_functions(project_root, include_paths=include_paths))
    violations.extend(detect_export_name_collisions(project_root, include_paths=include_paths))
    violations.extend(scan_policy_duplication_and_leakage(project_root, include_paths=include_paths))
    violations.extend(scan_formula_semantics_outside_policy(project_root, include_paths=include_paths))
    violations.extend(scan_package_root_surfaces(project_root, include_paths=include_paths))
    violations.extend(scan_route_expectations(call_edges))
    violations.extend(scan_owner_misuse(call_edges, registry))
    violations.extend(scan_factory_resolution_risks(constructor_edges))
    violations.extend(scan_provider_wiring(constructor_edges))
    violations.extend(scan_trace_contracts(project_root, include_paths=include_paths))
    violations.extend(scan_entrypoint_runtime_shortcuts(call_edges))
    violations.extend(scan_di_container_antipatterns(project_root, include_paths=include_paths))

    deduped = _dedupe_violations(violations)
    hard_gates = tuple(evaluate_hard_gates(deduped))
    hard_gates_passed = all(g.passed for g in hard_gates)
    subs = _build_subscores(registry, deduped)
    raw_score_100 = compute_raw_score_100(subs)
    admission_score_100 = compute_admission_score_100(raw_score_100, hard_gates_passed, bool(deduped))
    passed = admission_score_100 == REQUIRED_ARCHITECTURE_SCORE and hard_gates_passed and not deduped
    return ArchitectureReport(raw_score_100, admission_score_100, tuple(deduped), hard_gates, passed)


def run_operational_canon_checks(project_root: Path, registry: ManifestRegistry | None = None) -> ArchitectureReport:
    base = run_canon_checks(project_root, registry=registry, include_paths=OPERATIONAL_CANON_INCLUDE_PATHS)
    filtered = tuple(_filter_operational_false_positives(base.violations))
    hard_gates = tuple(evaluate_hard_gates(filtered))
    hard_gates_passed = all(g.passed for g in hard_gates)
    subs = _build_subscores(registry or ManifestRegistry.from_default_manifests(), filtered)
    raw_score_100 = compute_raw_score_100(subs)
    admission_score_100 = compute_admission_score_100(raw_score_100, hard_gates_passed, bool(filtered))
    passed = admission_score_100 == REQUIRED_ARCHITECTURE_SCORE and hard_gates_passed and not filtered
    return ArchitectureReport(raw_score_100, admission_score_100, filtered, hard_gates, passed)
