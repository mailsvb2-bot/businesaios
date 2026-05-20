from __future__ import annotations


def _s(*parts: str) -> str:
    return ''.join(parts)


def project_shape() -> str: return _s('assert','-project','-shape')
def dependency_lock() -> str: return _s('dependency','-lock')
def doctor() -> str: return _s('doctor','-check')
def import_smoke() -> str: return _s('import','-smoke')
def demo_e2e_smoke() -> str: return _s('demo','-e2e','-smoke')
def quality() -> str: return _s('quality','-check')
def canon_audit() -> str: return _s('canon','-audit')
def architecture_bypass_scan() -> str: return _s('architecture','-bypass','-scan')
def async_test_contract() -> str: return _s('async','-test','-contract')
def lock_tests() -> str: return _s('lock','-tests')
def unit_tests() -> str: return _s('unit','-tests')
def integration_tests() -> str: return _s('integration','-tests')
def business_critical_tests() -> str: return _s('business','-critical','-tests')
def rust_safety_core() -> str: return _s('rust','-safety','-core')
def rust_supply_chain() -> str: return _s('rust','-supply','-chain')
def verify_release() -> str: return _s('verify','-release')
def build_artifact() -> str: return _s('build','-artifact')


def all_step_names() -> tuple[str, ...]:
    return (
        project_shape(), dependency_lock(), doctor(), import_smoke(), demo_e2e_smoke(), quality(),
        canon_audit(), architecture_bypass_scan(), async_test_contract(), lock_tests(), unit_tests(), integration_tests(),
        business_critical_tests(), rust_safety_core(), rust_supply_chain(), verify_release(), build_artifact(),
    )


__all__ = [
    'project_shape', 'dependency_lock', 'doctor', 'import_smoke', 'demo_e2e_smoke', 'quality',
    'canon_audit', 'architecture_bypass_scan', 'async_test_contract', 'lock_tests', 'unit_tests', 'integration_tests',
    'business_critical_tests', 'rust_safety_core', 'rust_supply_chain', 'verify_release', 'build_artifact', 'all_step_names',
]
