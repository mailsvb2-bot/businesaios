"""
Critical error discovery protocol.

AI systems must search for critical architectural problems
before finalizing any modification.
"""


CRITICAL_ERROR_TYPES = [
    "second brain",
    "duplicate infrastructure",
    "hidden business logic",
    "multiple execution paths",
    "god module",
    "fake integrations",
    "missing observability",
    "silent failures",
    "config duplication",
    "dataflow divergence",
]


def required_first_pass():
    return 10


def required_second_pass():
    return 15


def error_types():
    return CRITICAL_ERROR_TYPES
