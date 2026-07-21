"""Single-owner scan for hidden decision-authority execution paths.

Implementation is split into passive AST/evidence helpers. This module remains
the sole compatibility and CLI surface; no helper may choose business actions
or execute effects.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

from canon.anti_second_brain_rules import (
    HARD_DECISION_AUTHORITY_METHODS,
    is_canonical_decision_owner_path,
)
from tools._decision_authority_scan.alias_context import (
    _alias_contexts,
    _AliasContextCollector,
)
from tools._decision_authority_scan.alias_scope import (
    _apply_alias_target,
    _comprehension_local_names,
    _scope_final_aliases,
    _scope_local_names,
)
from tools._decision_authority_scan.contracts import (
    GLOBAL_EXCLUDED_DIRS,
    ROOT_EXCLUDED_DIRS,
    Finding,
    _iter_python_files,
    _validated_repo_root,
)
from tools._decision_authority_scan.reflection import (
    _is_decision_mapping,
    _mapping_access,
    _reflection_factory,
    _reflection_lookup,
    _reflection_mutation,
)
from tools._decision_authority_scan.syntax import (
    _bound_names_in_target,
    _call_name,
    _expression_path,
    _is_authority_access,
    _is_direct_call_function,
    _normalized_receiver,
    _parent_map,
    _qualified_name,
    _receiver_looks_like_authority,
    _static_string,
)

CANON_DECISION_AUTHORITY_INDIRECT_SCAN = True
CANON_LEXICAL_AUTHORITY_ALIAS_RESOLUTION = True


def _scan_ast(
    *,
    rel: str,
    tree: ast.AST,
) -> list[Finding]:
    if is_canonical_decision_owner_path(rel):
        return []

    findings: list[Finding] = []
    parents = _parent_map(tree)
    aliases_by_node = _alias_contexts(tree)

    for node in ast.walk(tree):
        line = int(getattr(node, "lineno", 0) or 0)
        aliases = aliases_by_node.get(node, {})

        if isinstance(node, ast.ImportFrom):
            module_owner = str(node.module or "")
            for alias in node.names:
                if not alias.asname:
                    continue
                if _is_authority_access(module_owner, alias.name):
                    findings.append(
                        Finding(
                            "decision_authority_alias_import",
                            rel,
                            line,
                            f"{module_owner}.{alias.name} imported as "
                            f"{alias.asname}",
                        )
                    )

        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in HARD_DECISION_AUTHORITY_METHODS
            and not _is_direct_call_function(node, parents)
        ):
            findings.append(
                Finding(
                    "decision_authority_name_reference",
                    rel,
                    line,
                    f"{node.id} stored or exposed outside a canonical owner",
                )
            )

        if isinstance(node, ast.Attribute):
            owner = _expression_path(node.value, aliases)
            if (
                _is_authority_access(owner, node.attr)
                and not _is_direct_call_function(node, parents)
            ):
                findings.append(
                    Finding(
                        "decision_authority_method_reference",
                        rel,
                        line,
                        f"{owner}.{node.attr} stored or exposed outside "
                        "a canonical owner",
                    )
                )

        mapping = _mapping_access(node, aliases)
        if mapping is not None:
            target, method, mutation = mapping
            findings.append(
                Finding(
                    "decision_authority_mapping_mutation"
                    if mutation
                    else "decision_authority_mapping_lookup",
                    rel,
                    line,
                    f"{target}[{method or '<dynamic>'!r}] outside "
                    "a canonical owner",
                )
            )

        if not isinstance(node, ast.Call):
            continue

        owner, name = _call_name(node.func, aliases)
        if _is_authority_access(owner, name):
            target = f"{owner}.{name}" if owner else str(name)
            findings.append(
                Finding(
                    "decision_authority_call",
                    rel,
                    line,
                    f"{target}() outside a canonical owner",
                )
            )

        lookup = _reflection_lookup(node, aliases)
        if lookup is None:
            lookup = _reflection_factory(node, aliases, parents)
        if lookup is not None:
            target, method = lookup
            findings.append(
                Finding(
                    "decision_authority_dynamic_lookup",
                    rel,
                    line,
                    f"dynamic lookup of {target}.{method or '<dynamic>'}",
                )
            )

        mutation = _reflection_mutation(node, aliases)
        if mutation is not None:
            target, method = mutation
            findings.append(
                Finding(
                    "decision_authority_dynamic_mutation",
                    rel,
                    line,
                    f"dynamic mutation of {target}.{method or '<dynamic>'}",
                )
            )

    unique = {
        (item.code, item.path, item.line, item.detail): item
        for item in findings
    }
    return sorted(
        unique.values(),
        key=lambda item: (
            item.path,
            item.line,
            item.code,
            item.detail,
        ),
    )


def scan(root: Path | None = None) -> tuple[Finding, ...]:
    repo = _validated_repo_root(root or Path.cwd())
    findings: list[Finding] = []
    try:
        for path in _iter_python_files(repo):
            rel = path.relative_to(repo).as_posix()
            if is_canonical_decision_owner_path(rel):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                findings.append(
                    Finding(
                        "decision_authority_unscannable_source",
                        rel,
                        0,
                        f"source read failed: {type(exc).__name__}",
                    )
                )
                continue
            try:
                tree = ast.parse(text, filename=rel)
            except (SyntaxError, ValueError) as exc:
                findings.append(
                    Finding(
                        "decision_authority_unscannable_source",
                        rel,
                        int(getattr(exc, "lineno", 0) or 0),
                        f"source parse failed: {type(exc).__name__}",
                    )
                )
                continue
            findings.extend(_scan_ast(rel=rel, tree=tree))
    except RuntimeError as exc:
        findings.append(
            Finding(
                "decision_authority_scan_error",
                ".",
                0,
                str(exc),
            )
        )

    unique = {
        (item.code, item.path, item.line, item.detail): item
        for item in findings
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.path,
                item.line,
                item.code,
                item.detail,
            ),
        )
    )


def main() -> int:
    try:
        findings = scan(Path.cwd())
    except ValueError as exc:
        print(f"decision authority indirect scan failed: {exc}")
        return 1
    if not findings:
        print("decision authority indirect scan passed")
        return 0
    print(
        "decision authority indirect scan failed: "
        f"findings={len(findings)}"
    )
    for finding in findings[:80]:
        print(finding.format())
    if len(findings) > 80:
        print(f"... {len(findings) - 80} more finding(s)")
    return 1


__all__ = [
    "CANON_DECISION_AUTHORITY_INDIRECT_SCAN",
    "CANON_LEXICAL_AUTHORITY_ALIAS_RESOLUTION",
    "GLOBAL_EXCLUDED_DIRS",
    "ROOT_EXCLUDED_DIRS",
    "Finding",
    "_AliasContextCollector",
    "_alias_contexts",
    "_apply_alias_target",
    "_bound_names_in_target",
    "_call_name",
    "_comprehension_local_names",
    "_expression_path",
    "_is_authority_access",
    "_is_decision_mapping",
    "_is_direct_call_function",
    "_iter_python_files",
    "_mapping_access",
    "_normalized_receiver",
    "_parent_map",
    "_qualified_name",
    "_receiver_looks_like_authority",
    "_reflection_factory",
    "_reflection_lookup",
    "_reflection_mutation",
    "_scan_ast",
    "_scope_final_aliases",
    "_scope_local_names",
    "_static_string",
    "_validated_repo_root",
    "main",
    "os",
    "scan",
]

if __name__ == "__main__":
    raise SystemExit(main())
