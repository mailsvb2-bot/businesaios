from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any

from application.admin.platform_control_center.support import (
    BLOCK_EXCLUDE,
    SEVERITY_ORDER,
    SUSPICIOUS_NAME_HINTS,
    RiskRecommendation,
)

CANON_PLATFORM_CONTROL_CENTER_RISK_PROJECTION_LAYER = True

_NAME_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_MAX_RECOMMENDATION_FILES = 40
_MAX_RECOMMENDATIONS = 80
_MAX_CANDIDATE_FILES = 240
_MAX_DEPENDENCY_ROWS = 120
_MAX_CONFLICT_ROWS = 60
_MAX_VISUAL_ROWS = 80
_COMPAT_SURFACE_HINTS = {"compat", "legacy", "shim", "wrapper"}


def _require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _require_non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _require_positive_int(name: str, value: object) -> int:
    result = _require_non_negative_int(name, value)
    if result == 0:
        raise ValueError(f"{name} must be > 0")
    return result


def _iter_mapping_rows(name: str, values: Iterable[Mapping[str, Any]]) -> Iterator[Mapping[str, Any]]:
    if isinstance(values, (str, bytes, bytearray, Mapping)):
        raise ValueError(f"{name} must be an iterable of mappings")
    try:
        iterator = iter(values)
    except TypeError as exc:
        raise ValueError(f"{name} must be an iterable of mappings") from exc
    for row in iterator:
        if not isinstance(row, Mapping):
            raise ValueError(f"{name} must contain mappings")
        yield row


def _mapping_rows(name: str, values: Iterable[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    return tuple(_iter_mapping_rows(name, values))


def _name_tokens(value: str) -> set[str]:
    return {token for token in _NAME_TOKEN_RE.split(Path(value).stem.lower()) if token}


def _is_suspicious_surface_name(value: str) -> bool:
    stem = Path(value).stem.lower()
    tokens = _name_tokens(stem)
    return any(stem == hint or hint in tokens for hint in SUSPICIOUS_NAME_HINTS)


def _is_compat_surface_name(value: str) -> bool:
    stem = Path(value).stem.lower()
    tokens = _name_tokens(stem)
    return any(stem == hint or hint in tokens for hint in _COMPAT_SURFACE_HINTS)


@dataclass(frozen=True)
class RiskProjectionLayer:
    """Read-only architecture-risk projection.

    The layer reports evidence only. It does not choose business actions, mutate
    repository state, or execute any generated recommendation.
    """

    repo_root: Path

    def __post_init__(self) -> None:
        root = self.repo_root
        if isinstance(root, str):
            root = Path(root)
        if not isinstance(root, Path):
            raise ValueError("repo_root must be a path")
        try:
            resolved = root.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError("repo_root must exist") from exc
        if not resolved.is_dir():
            raise ValueError("repo_root must be a directory")
        object.__setattr__(self, "repo_root", resolved)

    def _top_level_blocks(self) -> Iterator[Path]:
        try:
            entries = sorted(self.repo_root.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise RuntimeError("failed to list repository root") from exc
        for path in entries:
            if path.is_symlink() or not path.is_dir() or path.name in BLOCK_EXCLUDE or path.name.startswith("."):
                continue
            yield path

    def _python_files(self, block: Path) -> tuple[Path, ...]:
        files: list[Path] = []
        try:
            candidates = block.rglob("*.py")
            for item in candidates:
                if not item.is_file() or item.is_symlink():
                    continue
                relative = item.relative_to(self.repo_root)
                if any(part in BLOCK_EXCLUDE or part.startswith(".") for part in relative.parts):
                    continue
                files.append(item)
        except (OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError(f"failed to scan block: {block.name}") from exc
        return tuple(sorted(files, key=lambda item: item.relative_to(self.repo_root).as_posix()))

    @staticmethod
    def _read_python_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ""

    def build_block_rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        python_files: list[dict[str, Any]] = []
        for path in self._top_level_blocks():
            py_files = self._python_files(path)
            if not py_files:
                continue
            python_lines = 0
            public_api_files = 0
            compat_files = 0
            large_files = 0
            for item in py_files:
                text = self._read_python_text(item)
                lines = sum(1 for line in text.splitlines() if line.strip())
                relative = item.relative_to(self.repo_root).as_posix()
                python_lines += lines
                public_api_files += int(item.name == "public_api.py")
                compat_files += int(_is_compat_surface_name(item.name))
                large_files += int(lines >= 450)
                python_files.append({"path": relative, "lines": lines, "block": path.name, "name": item.name})
            risk_score = compat_files * 2 + public_api_files + large_files
            maturity = "strong" if risk_score <= 2 else "watch" if risk_score <= 5 else "needs_work"
            rows.append(
                {
                    "block": path.name,
                    "python_files": len(py_files),
                    "python_lines": python_lines,
                    "public_api_files": public_api_files,
                    "compat_files": compat_files,
                    "large_files": large_files,
                    "risk_score": risk_score,
                    "maturity": maturity,
                }
            )
        return rows, python_files

    def build_risk_recommendations(
        self,
        *,
        block_rows: Iterable[Mapping[str, Any]],
        python_files: Iterable[Mapping[str, Any]],
    ) -> tuple[RiskRecommendation, ...]:
        validated_files: list[tuple[int, str, str]] = []
        for item in _mapping_rows("python_files", python_files):
            lines = _require_non_negative_int("lines", item.get("lines"))
            path = _require_text("path", item.get("path"))
            name = _require_text("name", item.get("name"))
            validated_files.append((lines, path, name))

        risks: list[RiskRecommendation] = []
        for lines, path, name in sorted(validated_files, key=lambda item: (-item[0], item[1]))[:_MAX_RECOMMENDATION_FILES]:
            if lines >= 700:
                risks.append(
                    RiskRecommendation(
                        file_path=path,
                        severity="critical",
                        risk_type="god_module_pressure",
                        summary="Large file is at risk of becoming a god module or hidden owner surface.",
                        recommended_change="Split the file into owner contracts, persistence/runtime helpers, and thin boundary adapters.",
                        change_target="smaller owner-shaped modules with one responsibility each",
                        possible_conflict="Large modules often accumulate mixed policy/execution/infrastructure semantics.",
                        line_hint=1,
                    )
                )
            elif lines >= 450:
                risks.append(
                    RiskRecommendation(
                        file_path=path,
                        severity="major",
                        risk_type="large_module",
                        summary="Module is getting large enough to hide mixed semantics and future regressions.",
                        recommended_change="Extract narrow helper modules and keep only the owner contract / orchestration entry in this file.",
                        change_target="owner contract + thin orchestration surface",
                        line_hint=1,
                    )
                )
            if _is_suspicious_surface_name(name):
                risks.append(
                    RiskRecommendation(
                        file_path=path,
                        severity="minor",
                        risk_type="surface_spread",
                        summary="Compat/public wrapper naming suggests boundary spread or alias layering.",
                        recommended_change="Reduce duplicate wrappers and keep one explicit canonical export per semantic surface.",
                        change_target="single canonical export or compat shim only",
                        line_hint=1,
                    )
                )

        for row in _mapping_rows("block_rows", block_rows):
            block = _require_text("block", row.get("block"))
            compat_files = _require_non_negative_int("compat_files", row.get("compat_files", 0))
            public_api_files = _require_non_negative_int("public_api_files", row.get("public_api_files", 0))
            if compat_files >= 8:
                risks.append(
                    RiskRecommendation(
                        file_path=f"{block}/",
                        severity="major",
                        risk_type="legacy_pressure",
                        summary="Block has a high count of compat/legacy surfaces and may hide duplicate ownership.",
                        recommended_change="Audit legacy/compat files in this block, keep one real owner surface, and reduce wrapper proliferation.",
                        change_target="single owner module per semantic surface",
                        possible_conflict="Wrapper drift and public API alias spread can mask real implementation ownership.",
                    )
                )
            if public_api_files >= 3:
                risks.append(
                    RiskRecommendation(
                        file_path=f"{block}/",
                        severity="minor",
                        risk_type="public_api_spread",
                        summary="Multiple public_api surfaces in one block can hide canonical ownership.",
                        recommended_change="Keep one explicit package owner export and demote other public_api surfaces to thin aliases or remove them.",
                        change_target="single explicit package export",
                    )
                )

        deduped: dict[tuple[str, str, str], RiskRecommendation] = {}
        for risk in risks:
            deduped.setdefault((risk.file_path, risk.risk_type, risk.summary), risk)
        ordered = sorted(
            deduped.values(),
            key=lambda item: (SEVERITY_ORDER.get(item.severity, 9), item.file_path, item.risk_type),
        )
        return tuple(ordered[:_MAX_RECOMMENDATIONS])

    def build_dependency_rows(self) -> list[dict[str, Any]]:
        counts: dict[tuple[str, str], int] = {}
        candidate_paths: list[Path] = []
        blocks = tuple(self._top_level_blocks())
        block_names = {path.name for path in blocks}
        for path in blocks:
            ranked = sorted(
                self._python_files(path),
                key=lambda item: (
                    0 if item.name in {"__init__.py", "public_api.py"} else 1,
                    len(item.relative_to(self.repo_root).parts),
                    item.relative_to(self.repo_root).as_posix(),
                ),
            )
            candidate_paths.extend(ranked[:10])
        for path in candidate_paths[:_MAX_CANDIDATE_FILES]:
            relative = path.relative_to(self.repo_root).as_posix()
            block = relative.split("/", 1)[0]
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, UnicodeError, SyntaxError):
                continue
            imported_blocks: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    candidates = (alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    candidates = (node.module or "",)
                else:
                    continue
                for candidate in candidates:
                    target = candidate.split(".", 1)[0]
                    if target in block_names and target != block:
                        imported_blocks.add(target)
            for target in imported_blocks:
                counts[(block, target)] = counts.get((block, target), 0) + 1
        rows = [
            {
                "source_block": source,
                "target_block": target,
                "import_count": count,
                "edge_kind": "cross_block_import",
                "graph_mode": "representative_scan",
            }
            for (source, target), count in counts.items()
        ]
        rows.sort(key=lambda row: (-row["import_count"], row["source_block"], row["target_block"]))
        return rows[:_MAX_DEPENDENCY_ROWS]

    def build_conflict_rows(
        self,
        *,
        block_rows: Iterable[Mapping[str, Any]],
        dependency_rows: Iterable[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        block_map: dict[str, Mapping[str, Any]] = {}
        for row in _mapping_rows("block_rows", block_rows):
            block = _require_text("block", row.get("block"))
            if block in block_map and dict(block_map[block]) != dict(row):
                raise ValueError("duplicate block row with conflicting evidence")
            block_map.setdefault(block, row)

        reverse_edges: dict[tuple[str, str], int] = {}
        for edge in _mapping_rows("dependency_rows", dependency_rows):
            source = _require_text("source_block", edge.get("source_block"))
            target = _require_text("target_block", edge.get("target_block"))
            if source == target:
                raise ValueError("dependency edge must cross blocks")
            count = _require_positive_int("import_count", edge.get("import_count"))
            key = (source, target)
            if key in reverse_edges and reverse_edges[key] != count:
                raise ValueError("duplicate dependency edge with conflicting evidence")
            reverse_edges.setdefault(key, count)

        rows: list[dict[str, Any]] = []
        for (source, target), count in reverse_edges.items():
            reverse = reverse_edges.get((target, source), 0)
            source_row = block_map.get(source, {})
            target_row = block_map.get(target, {})
            if reverse > 0:
                rows.append(
                    {
                        "conflict_kind": "bidirectional_dependency",
                        "source_block": source,
                        "target_block": target,
                        "summary": "Blocks import each other and risk ownership ambiguity.",
                        "recommended_change": "Move shared semantics into one owner block or extract a lower shared primitive.",
                        "possible_conflict": "Circular dependency or hidden dual ownership.",
                        "score": count + reverse,
                    }
                )
            elif _require_non_negative_int("compat_files", source_row.get("compat_files", 0)) >= 8 and _require_non_negative_int(
                "compat_files", target_row.get("compat_files", 0)
            ) >= 8:
                rows.append(
                    {
                        "conflict_kind": "legacy_overlap",
                        "source_block": source,
                        "target_block": target,
                        "summary": "Both blocks carry legacy pressure and import relation exists.",
                        "recommended_change": "Collapse wrappers and keep one explicit semantic owner between the connected blocks.",
                        "possible_conflict": "Compat surfaces can drift independently and mask true owner.",
                        "score": count,
                    }
                )
        rows.sort(key=lambda row: (-row["score"], row["source_block"], row["target_block"], row["conflict_kind"]))
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            source, target = sorted((row["source_block"], row["target_block"]))
            key = (source, target, row["conflict_kind"])
            if key not in seen:
                seen.add(key)
                unique.append(row)
        return unique[:_MAX_CONFLICT_ROWS]

    def build_visual_conflict_map(self, *, conflict_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        nodes: set[str] = set()
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in islice(_iter_mapping_rows("conflict_rows", conflict_rows), _MAX_VISUAL_ROWS):
            source = _require_text("source_block", row.get("source_block"))
            target = _require_text("target_block", row.get("target_block"))
            if source == target:
                raise ValueError("conflict edge must cross blocks")
            kind = _require_text("conflict_kind", row.get("conflict_kind"))
            score_value = row.get("score", 1)
            score = _require_positive_int("score", score_value)
            key = (source, target, kind)
            if key in seen:
                continue
            seen.add(key)
            nodes.update((source, target))
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "kind": kind,
                    "weight": score,
                    "summary": str(row.get("summary") or ""),
                    "click_endpoint": "/control-plane/admin/platform-ownership-drilldown",
                }
            )
        return {
            "nodes": [{"id": item, "label": item} for item in sorted(nodes)],
            "edges": edges,
            "render_mode": "force_graph",
            "legend": {"bidirectional_dependency": "amber", "legacy_overlap": "red"},
        }
