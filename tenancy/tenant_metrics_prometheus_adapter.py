from __future__ import annotations

import re
from typing import Iterable

from tenancy.tenant_metrics_contract import TenantMetricAggregate


CANON_TENANT_METRICS_PROMETHEUS_ADAPTER = True
_LABEL_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")


def _sanitize_metric_name(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(value or "").strip())
    if not text:
        raise ValueError("metric name is required")
    if text[0].isdigit():
        text = "tenant_" + text
    return text


def _sanitize_label_name(value: str) -> str:
    text = _LABEL_NAME_RE.sub("_", str(value or "").strip())
    if not text:
        raise ValueError("label name is required")
    if text[0].isdigit():
        text = "label_" + text
    return text


def _escape_label_value(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _render_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{_sanitize_label_name(key)}="{_escape_label_value(value)}"' for key, value in sorted(labels.items())]
    return "{" + ",".join(parts) + "}"


class TenantMetricsPrometheusAdapter:
    def render(self, *, aggregates: Iterable[TenantMetricAggregate]) -> str:
        lines: list[str] = []
        emitted_headers: set[str] = set()
        for aggregate in aggregates:
            aggregate.validate()
            metric_name = _sanitize_metric_name(aggregate.metric_name)
            labels = {"tenant_id": aggregate.tenant_id, **{str(k): str(v) for k, v in aggregate.labels.items()}}
            rendered_labels = _render_labels(labels)
            samples = {
                f"{metric_name}_total": aggregate.total,
                f"{metric_name}_last": aggregate.last_value,
                f"{metric_name}_min": aggregate.minimum,
                f"{metric_name}_max": aggregate.maximum,
                f"{metric_name}_samples": aggregate.sample_count,
            }
            for sample_name, sample_value in samples.items():
                if sample_name not in emitted_headers:
                    lines.append(f"# TYPE {sample_name} gauge")
                    emitted_headers.add(sample_name)
                lines.append(f"{sample_name}{rendered_labels} {sample_value}")
        return "\n".join(lines) + ("\n" if lines else "")


__all__ = ["CANON_TENANT_METRICS_PROMETHEUS_ADAPTER", "TenantMetricsPrometheusAdapter"]
