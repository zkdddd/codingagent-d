from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import STATE_DIR
from .run_log import summarize_run_log
from .run_log_viewer import find_run_log, run_log_timeline, summarize_run_for_display
from .run_self_check import analyze_run_health, format_run_health_report


def list_run_history(
    runs_dir: str | Path | None = None,
    *,
    status: str | None = None,
    health: str | None = None,
    quality_gate_status: str | None = None,
    validation_failed: bool | None = None,
    unverified: bool | None = None,
    failed_tools: bool | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return newest-first run summaries with optional debugging filters."""
    root = _runs_root(runs_dir)
    if not root.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in root.glob("*.jsonl"):
        if not path.is_file():
            continue
        row = _history_row(path)
        if row is None or not _matches_filters(
            row,
            status=status,
            health=health,
            quality_gate_status=quality_gate_status,
            validation_failed=validation_failed,
            unverified=unverified,
            failed_tools=failed_tools,
        ):
            continue
        rows.append(row)

    rows.sort(key=_sort_key, reverse=True)
    if limit is not None and limit >= 0:
        return rows[:limit]
    return rows


def export_run_markdown(
    run_id_or_path: str | Path,
    runs_dir: str | Path | None = None,
    *,
    timeline_limit: int = 80,
) -> str | None:
    path = _resolve_run_path(run_id_or_path, runs_dir)
    if path is None:
        return None

    lines = [
        "# Agent Run Export",
        "",
        f"- path: `{path}`",
        "",
        "## Summary",
        "",
        "```text",
        summarize_run_for_display(path),
        "```",
        "",
        "## Self Check",
        "",
        "```text",
        format_run_health_report(path),
        "```",
        "",
        "## Timeline",
        "",
    ]

    timeline = run_log_timeline(path)
    for item in timeline[:timeline_limit]:
        detail = f" - {item['detail']}" if item.get("detail") else ""
        lines.append(
            f"- {item.get('timestamp') or 'unknown'} | {item.get('title') or item.get('event')}{detail}"
        )
    if len(timeline) > timeline_limit:
        lines.append(f"- ... {len(timeline) - timeline_limit} more event(s)")
    return "\n".join(lines)


def export_latest_run_markdown(
    runs_dir: str | Path | None = None, *, timeline_limit: int = 80
) -> str | None:
    rows = list_run_history(runs_dir, limit=1)
    if not rows:
        return None
    return export_run_markdown(rows[0]["path"], runs_dir, timeline_limit=timeline_limit)


def _history_row(path: Path) -> dict[str, Any] | None:
    try:
        summary = summarize_run_log(path)
        health = analyze_run_health(path)
    except (OSError, ValueError):
        return None

    issues = health.get("issues") or []
    issue_codes = [str(issue.get("code") or "") for issue in issues if issue.get("code")]
    changed_paths = [str(item) for item in summary.get("changed_paths") or []]
    failed_tool_count = _failed_tool_count(health.get("failed_tools") or [])
    quality_gate = summary.get("quality_gate") if isinstance(summary.get("quality_gate"), dict) else {}

    return {
        "path": str(path),
        "run_id": summary.get("run_id"),
        "session_id": summary.get("session_id"),
        "workspace_root": summary.get("workspace_root"),
        "started_at": summary.get("started_at"),
        "finished_at": summary.get("finished_at"),
        "status": summary.get("status"),
        "health": health.get("health"),
        "trustworthy": health.get("trustworthy"),
        "validated": health.get("validated"),
        "validation_failed": health.get("validation_failed"),
        "unverified": "unverified_changes" in issue_codes,
        "failed_tool_count": failed_tool_count,
        "loop_warning_count": health.get("loop_warning_count", 0),
        "changed_path_count": len(changed_paths),
        "changed_paths": changed_paths,
        "event_count": summary.get("event_count", 0),
        "last_phase": summary.get("last_phase"),
        "issue_codes": issue_codes,
        "quality_gate_status": quality_gate.get("status"),
        "quality_gate_passed": quality_gate.get("passed"),
        "quality_gate_summary": quality_gate.get("summary"),
        "mtime": path.stat().st_mtime,
    }


def _matches_filters(
    row: dict[str, Any],
    *,
    status: str | None,
    health: str | None,
    quality_gate_status: str | None,
    validation_failed: bool | None,
    unverified: bool | None,
    failed_tools: bool | None,
) -> bool:
    if status is not None and row.get("status") != status:
        return False
    if health is not None and row.get("health") != health:
        return False
    if quality_gate_status is not None and row.get("quality_gate_status") != quality_gate_status:
        return False
    if validation_failed is not None and bool(row.get("validation_failed")) != validation_failed:
        return False
    if unverified is not None and bool(row.get("unverified")) != unverified:
        return False
    if failed_tools is not None and (int(row.get("failed_tool_count") or 0) > 0) != failed_tools:
        return False
    return True


def _resolve_run_path(run_id_or_path: str | Path, runs_dir: str | Path | None) -> Path | None:
    candidate = Path(run_id_or_path)
    if candidate.exists() and candidate.is_file():
        return candidate
    return find_run_log(str(run_id_or_path), _runs_root(runs_dir))


def _runs_root(runs_dir: str | Path | None) -> Path:
    return Path(runs_dir) if runs_dir is not None else Path(STATE_DIR) / "runs"


def _failed_tool_count(failed_tools: list[dict[str, str]]) -> int:
    total = 0
    for item in failed_tools:
        try:
            total += int(item.get("count") or 0)
        except (TypeError, ValueError):
            total += 1
    return total


def _sort_key(row: dict[str, Any]) -> tuple[str, float, str]:
    return (
        str(row.get("started_at") or ""),
        float(row.get("mtime") or 0),
        str(row.get("path") or ""),
    )
