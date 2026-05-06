from __future__ import annotations


def _s(*parts: str) -> str:
    return ''.join(parts)


def project_shape() -> str: return _s('assert','-project','-shape')
def doctor() -> str: return _s('doctor','-check')
def import_smoke() -> str: return _s('import','-smoke')
def quality() -> str: return _s('quality','-check')
def canon_audit() -> str: return _s('canon','-audit')
def lock_tests() -> str: return _s('lock','-tests')
def unit_tests() -> str: return _s('unit','-tests')
def integration_tests() -> str: return _s('integration','-tests')
def verify_release() -> str: return _s('verify','-release')
def build_artifact() -> str: return _s('build','-artifact')


def all_step_names() -> tuple[str, ...]:
    return (
        project_shape(), doctor(), import_smoke(), quality(), canon_audit(),
        lock_tests(), unit_tests(), integration_tests(), verify_release(), build_artifact(),
    )


__all__ = [
    'project_shape', 'doctor', 'import_smoke', 'quality', 'canon_audit',
    'lock_tests', 'unit_tests', 'integration_tests', 'verify_release',
    'build_artifact', 'all_step_names',
]
