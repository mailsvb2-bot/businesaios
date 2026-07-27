from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

CANON_BILLING_MONEY_FLOAT_SCANNER = True

_MONEY_TOKENS = (
    "amount",
    "balance",
    "budget",
    "charge",
    "fee",
    "invoice",
    "minor",
    "payment",
    "price",
    "quantity",
    "refund",
    "revenue",
    "spend",
    "unit_price",
)
_TENANCY_MONEY_FILES = (
    "tenancy/tenant_billing_scope.py",
    "tenancy/tenant_execution_budget_guard.py",
    "tenancy/tenant_policy_store.py",
    "tenancy/tenant_quota_guard.py",
    "tenancy/tenant_runtime_limits.py",
)


@dataclass(frozen=True)
class MoneyFloatViolation:
    path: str
    line: int
    expression: str
    rule: str


def _candidate_files(root: Path) -> tuple[Path, ...]:
    files = [*root.joinpath("billing").rglob("*.py")]
    files.extend(root.joinpath("lead_outcomes").rglob("*.py"))
    files.extend(root / relative for relative in _TENANCY_MONEY_FILES)
    return tuple(sorted(path for path in files if path.is_file()))


def _contains_money_token(expression: str) -> bool:
    normalized = expression.casefold()
    return any(token in normalized for token in _MONEY_TOKENS)


def scan_billing_money_float_arithmetic(root: Path) -> tuple[MoneyFloatViolation, ...]:
    violations: list[MoneyFloatViolation] = []
    for path in _candidate_files(root.resolve()):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            expression = ast.get_source_segment(source, node) or ""
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"float", "round"}
                and _contains_money_token(expression)
            ):
                violations.append(
                    MoneyFloatViolation(
                        path=path.relative_to(root).as_posix(),
                        line=node.lineno,
                        expression=" ".join(expression.split()),
                        rule=f"direct_{node.func.id}_money_operation",
                    )
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "defaultdict"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "float"
            ):
                violations.append(
                    MoneyFloatViolation(
                        path=path.relative_to(root).as_posix(),
                        line=node.lineno,
                        expression="defaultdict(float)",
                        rule="float_money_accumulator",
                    )
                )
            if isinstance(node, ast.BinOp) and _contains_money_token(expression):
                has_float_literal = any(
                    isinstance(child, ast.Constant)
                    and isinstance(child.value, float)
                    for child in ast.walk(node)
                )
                if has_float_literal:
                    violations.append(
                        MoneyFloatViolation(
                            path=path.relative_to(root).as_posix(),
                            line=node.lineno,
                            expression=" ".join(expression.split()),
                            rule="float_literal_money_arithmetic",
                        )
                    )
    unique = {
        (item.path, item.line, item.expression, item.rule): item
        for item in violations
    }
    return tuple(unique[key] for key in sorted(unique))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations = scan_billing_money_float_arithmetic(root)
    if violations:
        for item in violations:
            print(f"{item.path}:{item.line}: {item.rule}: {item.expression}")
        return 1
    print("billing money float scanner passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
