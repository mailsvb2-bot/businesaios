from __future__ import annotations


def headline(*, level: str, code: str) -> str:
    return f"[{str(level).upper()}] Messaging policy alert: {str(code)}"


def detail_line(*, title: str, detail: str) -> str:
    return f"{str(title)} — {str(detail)}"


def context_line(*, tenant_id: str, user_id: str, date_from: str, date_to: str) -> str:
    return f"tenant_id={tenant_id}; user_id={user_id or '-'}; date_from={date_from or '-'}; date_to={date_to or '-'}"


def metric_line(*, metric_name: str, metric_value: float, threshold_value: float) -> str:
    return f"{metric_name}={metric_value}; threshold={threshold_value}"
