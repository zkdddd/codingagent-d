from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..config import STATE_DIR
from .run_log import latest_run_log, read_run_events, summarize_run_log


def find_run_log(run_id: str, runs_dir: str | Path | None = None) -> Path | None:
    root = _runs_root(runs_dir)
    if not run_id or not root.exists():
        return None

    candidates = sorted(root.glob(f"*{run_id}*.jsonl"))
    for path in candidates:
        if path.is_file() and _log_matches_run_id(path, run_id):
            return path
    return None


def run_log_timeline(path: str | Path) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for event in read_run_events(path):
        event_type = str(event.get("event") or "unknown")
        data = _event_data(event)
        item = {
            "timestamp": event.get("timestamp"),
            "event": event_type,
            "title": _timeline_title(event_type, data),
        }
        detail = _timeline_detail(event_type, data)
        if detail:
            item["detail"] = detail
        timeline.append(item)
    return timeline


def summarize_run_for_display(path: str | Path) -> str:
    summary = summarize_run_log(path)
    events = read_run_events(path)

    tool_names = _tool_name_counts(events)
    failed_tools = _failed_tools(events)
    warnings = _event_titles(events, "tool_loop_warning")
    patch_recoveries = _event_titles(events, "patch_recovery")
    failure_focus = _event_titles(events, "failure_focus")
    model_requests = _model_request_counts(events)
    model_fallbacks = _model_fallback_count(events)
    model_errors = _model_error_titles(events)

    lines = [
        "Run Log Summary",
        f"- run_id: {summary.get('run_id') or 'unknown'}",
        f"- status: {summary.get('status') or 'running/unknown'}",
        f"- workspace: {summary.get('workspace_root') or 'unknown'}",
        f"- started_at: {summary.get('started_at') or 'unknown'}",
        f"- finished_at: {summary.get('finished_at') or 'not finished'}",
        f"- events: {summary.get('event_count', 0)}",
        f"- last_phase: {summary.get('last_phase') or 'unknown'}",
    ]

    if tool_names:
        lines.append("- tools: " + _format_counts(tool_names))
    else:
        lines.append("- tools: none")

    if model_requests:
        lines.append("- model_requests: " + _format_counts(model_requests))
    else:
        lines.append("- model_requests: none")
    if model_fallbacks:
        lines.append(f"- model_fallbacks: {model_fallbacks}")
    if model_errors:
        lines.append("- model_errors: " + "; ".join(model_errors))

    if failed_tools:
        lines.append("- failed_tools: " + ", ".join(failed_tools))

    validation = summary.get("last_validation_summary")
    if validation:
        status = "failed" if summary.get("validation_failed") else "passed/recorded"
        lines.append(f"- validation: {status}: {validation}")

    changed_paths = summary.get("changed_paths") or []
    if changed_paths:
        lines.append("- changed_paths: " + ", ".join(str(path) for path in changed_paths))

    if warnings:
        lines.append("- loop_warnings: " + "; ".join(warnings))
    if patch_recoveries:
        lines.append("- patch_recovery: " + "; ".join(patch_recoveries))
    if failure_focus:
        lines.append("- failure_focus: " + "; ".join(failure_focus))

    return "\n".join(lines)


def summarize_latest_run_for_display(runs_dir: str | Path | None = None) -> str | None:
    path = latest_run_log(_runs_root(runs_dir))
    if path is None:
        return None
    return summarize_run_for_display(path)


def _runs_root(runs_dir: str | Path | None) -> Path:
    return Path(runs_dir) if runs_dir is not None else Path(STATE_DIR) / "runs"


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _log_matches_run_id(path: Path, run_id: str) -> bool:
    try:
        events = read_run_events(path)
    except ValueError:
        return False
    return any(str(event.get("run_id") or "") == run_id for event in events)


def _tool_name_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "tool_call":
            continue
        name = _event_data(event).get("name")
        if name:
            counts[str(name)] += 1
    return counts


def _failed_tools(events: list[dict[str, Any]]) -> list[str]:
    failed: list[str] = []
    for event in events:
        if event.get("event") != "tool_result":
            continue
        data = _event_data(event)
        if _result_ok(data):
            continue
        name = str(data.get("name") or "unknown")
        detail = _short_text(
            data.get("summary")
            or data.get("error")
            or _nested_result_value(data, "summary")
            or _nested_result_value(data, "error")
        )
        failed.append(f"{name} ({detail})" if detail else name)
    return failed


def _model_request_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "model_request":
            continue
        data = _event_data(event)
        model = str(data.get("model") or "unknown")
        reasoning = data.get("reasoning_effort")
        label = f"{model}/{reasoning}" if reasoning else f"{model}/no-reasoning"
        if data.get("fallback_without_reasoning"):
            label += " fallback"
        counts[label] += 1
    return counts


def _model_fallback_count(events: list[dict[str, Any]]) -> int:
    return sum(
        1
        for event in events
        if event.get("event") == "model_response"
        and bool(_event_data(event).get("fallback_without_reasoning"))
    )


def _model_error_titles(events: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for event in events:
        if event.get("event") != "model_error":
            continue
        data = _event_data(event)
        model = data.get("model") or "unknown"
        error_type = data.get("error_type") or "error"
        detail = _short_text(data.get("error"))
        errors.append(f"{model} {error_type}: {detail}" if detail else f"{model} {error_type}")
    return errors


def _result_ok(data: dict[str, Any]) -> bool:
    if "ok" in data:
        return bool(data.get("ok"))
    result = data.get("result")
    if isinstance(result, dict) and "ok" in result:
        return bool(result.get("ok"))
    return True


def _nested_result_value(data: dict[str, Any], key: str) -> Any:
    result = data.get("result")
    return result.get(key) if isinstance(result, dict) else None


def _event_titles(events: list[dict[str, Any]], event_type: str) -> list[str]:
    titles: list[str] = []
    for event in events:
        if event.get("event") != event_type:
            continue
        title = _timeline_detail(event_type, _event_data(event)) or _timeline_title(
            event_type, _event_data(event)
        )
        if title:
            titles.append(title)
    return titles


def _timeline_title(event_type: str, data: dict[str, Any]) -> str:
    if event_type == "run_start":
        return "Run started"
    if event_type == "run_finish":
        return f"Run finished: {data.get('status') or 'unknown'}"
    if event_type == "agent_status":
        return f"Phase: {data.get('phase') or 'unknown'}"
    if event_type == "tool_call":
        return f"Tool call: {data.get('name') or 'unknown'}"
    if event_type == "tool_result":
        name = data.get("name") or "unknown"
        return f"Tool result: {name} ({'ok' if _result_ok(data) else 'failed'})"
    if event_type == "model_request":
        model = data.get("model") or "unknown"
        effort = data.get("reasoning_effort") or "no-reasoning"
        suffix = " fallback" if data.get("fallback_without_reasoning") else ""
        return f"Model request: {model}/{effort}{suffix}"
    if event_type == "model_response":
        model = data.get("model") or "unknown"
        effort = data.get("reasoning_effort") or "no-reasoning"
        return f"Model response: {model}/{effort}"
    if event_type == "model_error":
        model = data.get("model") or "unknown"
        error_type = data.get("error_type") or "error"
        return f"Model error: {model} ({error_type})"
    if event_type == "validation_plan":
        return "Validation plan"
    if event_type == "focused_validation_plan":
        return "Focused validation plan"
    if event_type == "change_plan":
        plan = data.get("plan") if isinstance(data.get("plan"), dict) else data
        return f"Change plan: {plan.get('operation') or plan.get('tool_name') or 'change'}"
    if event_type == "tool_loop_warning":
        return "Tool loop warning"
    if event_type == "patch_recovery":
        return "Patch recovery"
    if event_type == "failure_focus":
        return "Failure focus"
    return event_type


def _timeline_detail(event_type: str, data: dict[str, Any]) -> str | None:
    if event_type == "agent_status":
        return _short_text(data.get("detail"))
    if event_type in {"tool_call", "tool_result"}:
        return _short_text(data.get("summary") or data.get("error"))
    if event_type in {"model_request", "model_response"}:
        parts = []
        if data.get("duration_ms") is not None:
            parts.append(f"{data.get('duration_ms')}ms")
        if data.get("has_tools"):
            parts.append("tools")
        if data.get("stream"):
            parts.append("stream")
        if data.get("fallback_without_reasoning"):
            parts.append("fallback without reasoning")
        return ", ".join(parts) if parts else None
    if event_type == "model_error":
        return _short_text(data.get("error"))
    if event_type == "run_finish":
        return _short_text(data.get("last_validation_summary") or data.get("summary"))
    if event_type == "tool_loop_warning":
        return _short_text(data.get("message") or data.get("reason") or data.get("warning"))
    if event_type == "patch_recovery":
        return _short_text(data.get("prompt") or data.get("message") or data.get("summary"))
    if event_type == "failure_focus":
        targets = data.get("targets")
        if isinstance(targets, list):
            return f"{len(targets)} target(s)"
    return None


def _format_counts(counts: Counter[str]) -> str:
    return ", ".join(f"{name} x{count}" for name, count in counts.most_common())


def _short_text(value: Any, limit: int = 160) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
