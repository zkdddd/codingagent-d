from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..config import STATE_DIR
from .run_log import latest_run_log, read_run_events, summarize_run_log
from .run_log_viewer import find_run_log

PASS = "pass"
WARN = "warn"
FAIL = "fail"


def analyze_run_health(path: str | Path) -> dict[str, Any]:
    events = read_run_events(path)
    summary = summarize_run_log(path)
    finish = _last_event(events, "run_finish")
    finish_data = _event_data(finish)
    issues: list[dict[str, str]] = []

    status = str(summary.get("status") or "")
    changed_paths = [str(path) for path in summary.get("changed_paths") or []]
    validated = bool(finish_data.get("validated"))
    validation_failed = bool(summary.get("validation_failed"))
    failed_tools = _failed_tools(events)
    loop_warning_count = _event_count(events, "tool_loop_warning")

    if finish is None:
        issues.append(
            _issue(
                FAIL,
                "run_not_finished",
                "Run log has no finish event; the Agent may have crashed or been interrupted.",
            )
        )
    elif status != "completed":
        issues.append(
            _issue(
                FAIL,
                "run_not_completed",
                f"Run finished with status `{status or 'unknown'}`.",
            )
        )

    if changed_paths and not validated:
        issues.append(
            _issue(
                FAIL,
                "unverified_changes",
                "Code changes were recorded, but validation did not run or did not complete.",
            )
        )

    if validation_failed:
        detail = str(summary.get("last_validation_summary") or "Validation failed.")
        issues.append(_issue(FAIL, "validation_failed", detail))

    if failed_tools:
        issues.append(
            _issue(
                WARN,
                "failed_tools",
                f"{len(failed_tools)} tool result(s) failed during the run.",
            )
        )

    if loop_warning_count:
        issues.append(
            _issue(
                WARN,
                "loop_warning",
                f"{loop_warning_count} loop warning(s) were emitted.",
            )
        )

    health = _overall_health(issues)
    return {
        "health": health,
        "trustworthy": health == PASS,
        "run_id": summary.get("run_id"),
        "status": summary.get("status"),
        "validated": validated,
        "validation_failed": validation_failed,
        "changed_paths": changed_paths,
        "failed_tools": failed_tools,
        "loop_warning_count": loop_warning_count,
        "patch_recovery_count": _event_count(events, "patch_recovery"),
        "failure_focus_count": _event_count(events, "failure_focus"),
        "event_count": summary.get("event_count", 0),
        "last_phase": summary.get("last_phase"),
        "issues": issues,
    }


def format_run_health_report(path: str | Path) -> str:
    health = analyze_run_health(path)
    lines = [
        "Agent Self Check",
        f"- health: {health['health']}",
        f"- trustworthy: {'yes' if health['trustworthy'] else 'no'}",
        f"- run_id: {health.get('run_id') or 'unknown'}",
        f"- status: {health.get('status') or 'running/unknown'}",
        f"- validated: {'yes' if health.get('validated') else 'no'}",
        f"- validation_failed: {'yes' if health.get('validation_failed') else 'no'}",
        f"- changed_paths: {', '.join(health['changed_paths']) if health['changed_paths'] else 'none'}",
        f"- failed_tools: {_format_failed_tools(health['failed_tools'])}",
        f"- loop_warnings: {health['loop_warning_count']}",
        f"- patch_recoveries: {health['patch_recovery_count']}",
        f"- failure_focus_reads: {health['failure_focus_count']}",
    ]
    issues = health.get("issues") or []
    if issues:
        lines.append("- issues:")
        for issue in issues:
            lines.append(f"  - [{issue['severity']}] {issue['code']}: {issue['message']}")
    else:
        lines.append("- issues: none")
    return "\n".join(lines)


def analyze_latest_run_health(runs_dir: str | Path | None = None) -> dict[str, Any] | None:
    path = latest_run_log(_runs_root(runs_dir))
    if path is None:
        return None
    return analyze_run_health(path)


def analyze_run_health_by_id(
    run_id: str, runs_dir: str | Path | None = None
) -> dict[str, Any] | None:
    path = find_run_log(run_id, _runs_root(runs_dir))
    if path is None:
        return None
    return analyze_run_health(path)


def _runs_root(runs_dir: str | Path | None) -> Path:
    return Path(runs_dir) if runs_dir is not None else Path(STATE_DIR) / "runs"


def _event_data(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {}
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _last_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    return next((event for event in reversed(events) if event.get("event") == event_type), None)


def _event_count(events: list[dict[str, Any]], event_type: str) -> int:
    return sum(1 for event in events if event.get("event") == event_type)


def _failed_tools(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    counts: Counter[str] = Counter()
    details: dict[str, str] = {}
    for event in events:
        if event.get("event") != "tool_result":
            continue
        data = _event_data(event)
        if _result_ok(data):
            continue
        name = str(data.get("name") or "unknown")
        counts[name] += 1
        details.setdefault(name, _short_text(_result_detail(data)) or "")
    return [
        {"name": name, "count": str(count), "detail": details.get(name, "")}
        for name, count in counts.most_common()
    ]


def _result_ok(data: dict[str, Any]) -> bool:
    if "ok" in data:
        return bool(data.get("ok"))
    result = data.get("result")
    if isinstance(result, dict) and "ok" in result:
        return bool(result.get("ok"))
    return True


def _result_detail(data: dict[str, Any]) -> Any:
    result = data.get("result")
    nested = result if isinstance(result, dict) else {}
    return data.get("summary") or data.get("error") or nested.get("summary") or nested.get("error")


def _issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def _overall_health(issues: list[dict[str, str]]) -> str:
    severities = {issue.get("severity") for issue in issues}
    if FAIL in severities:
        return FAIL
    if WARN in severities:
        return WARN
    return PASS


def _format_failed_tools(failed_tools: list[dict[str, str]]) -> str:
    if not failed_tools:
        return "none"
    parts = []
    for item in failed_tools:
        detail = f": {item['detail']}" if item.get("detail") else ""
        parts.append(f"{item['name']} x{item['count']}{detail}")
    return ", ".join(parts)


def _short_text(value: Any, limit: int = 140) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
