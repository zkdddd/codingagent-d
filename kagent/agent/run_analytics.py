from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .run_history import list_run_history
from .run_log import read_run_events


def build_run_analytics(
    runs_dir: str | Path | None = None,
    *,
    limit: int = 50,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    rows = list_run_history(runs_dir, limit=max(0, int(limit)))
    workspace = str(workspace_root or "").strip()
    if workspace:
        rows = [row for row in rows if str(row.get("workspace_root") or "").strip() == workspace]
    counters = _base_counters(rows)
    issue_counts: Counter[str] = Counter()
    gate_check_counts: Counter[str] = Counter()
    failed_tool_counts: Counter[str] = Counter()
    model_error_counts: Counter[str] = Counter()
    validation_command_counts: Counter[str] = Counter()

    for row in rows:
        for issue in row.get("issue_codes") or []:
            issue_counts[str(issue)] += 1
        events = _safe_read_events(row.get("path"))
        gate_check_counts.update(_gate_check_counts(events))
        failed_tool_counts.update(_failed_tool_counts(events))
        model_error_counts.update(_model_error_counts(events))
        validation_command_counts.update(_validation_command_counts(events))

    run_count = len(rows)
    return {
        "run_count": run_count,
        "status_counts": dict(counters["status"]),
        "health_counts": dict(counters["health"]),
        "quality_gate_counts": dict(counters["quality_gate"]),
        "validation_failed_count": counters["flags"].get("validation_failed", 0),
        "unverified_count": counters["flags"].get("unverified", 0),
        "failed_tool_run_count": counters["flags"].get("failed_tools", 0),
        "model_error_run_count": counters["flags"].get("model_errors", 0),
        "validation_failed_rate": _rate(counters["flags"].get("validation_failed", 0), run_count),
        "unverified_rate": _rate(counters["flags"].get("unverified", 0), run_count),
        "failed_tool_run_rate": _rate(counters["flags"].get("failed_tools", 0), run_count),
        "model_error_run_rate": _rate(counters["flags"].get("model_errors", 0), run_count),
        "top_issue_codes": _top_items(issue_counts),
        "top_quality_gate_checks": _top_items(gate_check_counts),
        "top_failed_tools": _top_items(failed_tool_counts),
        "top_model_errors": _top_items(model_error_counts),
        "top_validation_commands": _top_items(validation_command_counts),
        "recent_problem_runs": _recent_problem_runs(rows),
    }


def format_run_analytics_markdown(analytics: dict[str, Any]) -> str:
    lines = [
        "# Run Analytics",
        "",
        f"- runs: `{analytics.get('run_count') or 0}`",
        f"- validation_failed_rate: `{analytics.get('validation_failed_rate') or 0}`",
        f"- unverified_rate: `{analytics.get('unverified_rate') or 0}`",
        f"- failed_tool_run_rate: `{analytics.get('failed_tool_run_rate') or 0}`",
        f"- model_error_run_rate: `{analytics.get('model_error_run_rate') or 0}`",
        "",
        "## Status",
        "",
    ]
    lines.extend(_counter_lines(analytics.get("status_counts")))
    lines.extend(["", "## Health", ""])
    lines.extend(_counter_lines(analytics.get("health_counts")))
    lines.extend(["", "## Quality Gate", ""])
    lines.extend(_counter_lines(analytics.get("quality_gate_counts")))
    lines.extend(["", "## Top Issue Codes", ""])
    lines.extend(_top_lines(analytics.get("top_issue_codes")))
    lines.extend(["", "## Top Gate Checks", ""])
    lines.extend(_top_lines(analytics.get("top_quality_gate_checks")))
    lines.extend(["", "## Top Failed Tools", ""])
    lines.extend(_top_lines(analytics.get("top_failed_tools")))
    lines.extend(["", "## Top Model Errors", ""])
    lines.extend(_top_lines(analytics.get("top_model_errors")))
    lines.extend(["", "## Top Validation Commands", ""])
    lines.extend(_top_lines(analytics.get("top_validation_commands")))
    lines.extend(["", "## Recent Problem Runs", ""])
    lines.extend(_problem_run_lines(analytics.get("recent_problem_runs")))
    return "\n".join(lines)


def _base_counters(rows: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    status_counts: Counter[str] = Counter()
    health_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    for row in rows:
        status_counts[str(row.get("status") or "running/unknown")] += 1
        health_counts[str(row.get("health") or "unknown")] += 1
        gate_counts[str(row.get("quality_gate_status") or "unknown")] += 1
        if row.get("validation_failed"):
            flags["validation_failed"] += 1
        if row.get("unverified"):
            flags["unverified"] += 1
        if int(row.get("failed_tool_count") or 0) > 0:
            flags["failed_tools"] += 1
        if _row_has_model_errors(row):
            flags["model_errors"] += 1
    return {"status": status_counts, "health": health_counts, "quality_gate": gate_counts, "flags": flags}


def _row_has_model_errors(row: dict[str, Any]) -> bool:
    events = _safe_read_events(row.get("path"))
    return any(event.get("event") == "model_error" for event in events)


def _safe_read_events(path: Any) -> list[dict[str, Any]]:
    try:
        return read_run_events(str(path))
    except (OSError, ValueError, TypeError):
        return []


def _gate_check_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    finish_data = _last_event_data(events, "run_finish")
    final_trust = finish_data.get("final_trust") if isinstance(finish_data.get("final_trust"), dict) else {}
    gate = final_trust.get("quality_gate") if isinstance(final_trust.get("quality_gate"), dict) else {}
    checks = gate.get("checks") if isinstance(gate.get("checks"), list) else []
    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status") or "unknown")
        code = str(check.get("code") or "unknown")
        if status in {"fail", "warn"}:
            counts[f"{status}:{code}"] += 1
    return counts


def _failed_tool_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "tool_result":
            continue
        data = _event_data(event)
        if _result_ok(data):
            continue
        counts[str(data.get("name") or "unknown")] += 1
    return counts


def _model_error_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "model_error":
            continue
        data = _event_data(event)
        model = str(data.get("model") or "unknown")
        error_type = str(data.get("error_type") or "error")
        counts[f"{model}:{error_type}"] += 1
    return counts


def _validation_command_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "tool_result":
            continue
        data = _event_data(event)
        if data.get("name") != "run_command":
            continue
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        command = str(args.get("command") or "").strip()
        if command:
            counts[command] += 1
    return counts


def _recent_problem_runs(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        gate = str(row.get("quality_gate_status") or "")
        if (
            row.get("health") in {"fail", "warn"}
            or gate in {"fail", "warn"}
            or row.get("validation_failed")
            or row.get("unverified")
            or int(row.get("failed_tool_count") or 0) > 0
        ):
            selected.append(
                {
                    "run_id": row.get("run_id"),
                    "status": row.get("status"),
                    "health": row.get("health"),
                    "quality_gate_status": row.get("quality_gate_status"),
                    "validation_failed": bool(row.get("validation_failed")),
                    "unverified": bool(row.get("unverified")),
                    "failed_tool_count": int(row.get("failed_tool_count") or 0),
                    "changed_paths": row.get("changed_paths") or [],
                }
            )
        if len(selected) >= limit:
            break
    return selected


def _last_event_data(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for event in reversed(events):
        if event.get("event") == event_type:
            return _event_data(event)
    return {}


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _result_ok(data: dict[str, Any]) -> bool:
    if "ok" in data:
        return bool(data.get("ok"))
    result = data.get("result")
    if isinstance(result, dict):
        if "ok" in result:
            return bool(result.get("ok"))
        if "returncode" in result:
            return int(result.get("returncode") or 0) == 0
    return True


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 3)


def _top_items(counter: Counter[str], limit: int = 8) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def _counter_lines(value: Any) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- none"]
    return [f"- `{key}`: {count}" for key, count in sorted(value.items())]


def _top_lines(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- none"]
    return [f"- `{item.get('name')}`: {item.get('count')}" for item in items if isinstance(item, dict)]


def _problem_run_lines(value: Any) -> list[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- none"]
    lines: list[str] = []
    for row in rows:
        bits = [
            f"status `{row.get('status') or 'unknown'}`",
            f"health `{row.get('health') or 'unknown'}`",
            f"gate `{row.get('quality_gate_status') or 'unknown'}`",
        ]
        if row.get("validation_failed"):
            bits.append("validation_failed")
        if row.get("unverified"):
            bits.append("unverified")
        failed_tool_count = int(row.get("failed_tool_count") or 0)
        if failed_tool_count:
            bits.append(f"failed_tools `{failed_tool_count}`")
        lines.append(f"- `{str(row.get('run_id') or 'unknown')[:10]}` - " + ", ".join(bits))
    return lines
