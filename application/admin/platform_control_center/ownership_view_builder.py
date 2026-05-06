from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from application.admin.platform_control_center.support import RiskRecommendation

CANON_PLATFORM_CONTROL_CENTER_OWNERSHIP_VIEW_BUILDER = True


@dataclass(frozen=True)
class OwnershipViewBuilder:
    def build_ownership_rows(self, *, block_rows: Iterable[Mapping[str, Any]], dependency_rows: Iterable[Mapping[str, Any]], risks: Iterable[RiskRecommendation]) -> list[dict[str, Any]]:
        risk_counts: dict[str, int] = {}
        for item in risks:
            block = str(item.file_path).split('/', 1)[0]
            risk_counts[block] = risk_counts.get(block, 0) + 1
        imports_from: dict[str, int] = {}
        imports_to: dict[str, int] = {}
        for row in dependency_rows:
            source = str(row['source_block'])
            target = str(row['target_block'])
            count = int(row['import_count'])
            imports_from[source] = imports_from.get(source, 0) + count
            imports_to[target] = imports_to.get(target, 0) + count
        rows: list[dict[str, Any]] = []
        for block in block_rows:
            block_name = str(block['block'])
            outbound = imports_from.get(block_name, 0)
            inbound = imports_to.get(block_name, 0)
            owner_strength = max(1, inbound - outbound + 5 - risk_counts.get(block_name, 0))
            rows.append({
                'block': block_name,
                'owner_strength': owner_strength,
                'inbound_edges': inbound,
                'outbound_edges': outbound,
                'risk_count': risk_counts.get(block_name, 0),
                'owner_status': 'strong_owner' if owner_strength >= 6 else 'watch_owner' if owner_strength >= 3 else 'weak_owner',
                'recommended_change': 'Keep semantics here and pull wrappers down.' if inbound >= outbound else 'Consider moving shared semantics to a lower common owner.',
            })
        rows.sort(key=lambda row: (-int(row['owner_strength']), row['block']))
        return rows[:80]

    def build_ownership_graph(self, *, ownership_rows: Iterable[Mapping[str, Any]], dependency_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        rows = list(ownership_rows)
        return {
            'ownership_rows': rows,
            'graph_rows': list(dependency_rows),
            'ownership_graph_ui': {
                'kind': 'clickable_graph_navigation',
                'node_key': 'block',
                'edge_source': 'source_block',
                'edge_target': 'target_block',
                'weight': 'import_count',
                'drilldown_endpoint': '/control-plane/admin/platform-ownership-drilldown',
            },
        }
