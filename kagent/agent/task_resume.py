from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import STATE_DIR
from .run_log import latest_run_log, read_run_events, summarize_run_log
from .run_log_viewer import find_run_log
from .run_self_check import analyze_run_health


def build_resume_context(path: str | Path) -> dict[str, Any]:
    events = read_run_events(path)
    summary = summarize_run_log(path)
    finish_data = _event_data(_last_event(events, "run_finish"))
    health = analyze_run_health(path)
    plan_snapshot = _plan_snapshot(events, finish_data)
    next_action = _next_action(plan_snapshot)
    changed_paths = [str(item) for item in summary.get("changed_paths") or []]
    validation_summary = summary.get("last_validation_summary")
    failed_tools = health.get("failed_tools") or []
    quality_gate = summary.get("quality_gate") if isinstance(summary.get("quality_gate"), dict) else {}
    quality_gate_checks = _quality_gate_checks(quality_gate)
    issue_codes = [
        str(issue.get("code"))
        for issue in health.get("issues", [])
        if isinstance(issue, dict) and issue.get("code")
    ]

    priority = _resume_priority(
        status=str(summary.get("status") or ""),
        next_action=next_action,
        changed_paths=changed_paths,
        validation_failed=bool(summary.get("validation_failed")),
        failed_tools=failed_tools,
        issue_codes=issue_codes,
        quality_gate=quality_gate,
    )
    prompt = _resume_prompt(
        summary=summary,
        health=health,
        priority=priority,
        next_action=next_action,
        changed_paths=changed_paths,
        validation_summary=validation_summary,
        failed_tools=failed_tools,
        issue_codes=issue_codes,
        quality_gate=quality_gate,
        quality_gate_checks=quality_gate_checks,
    )
    return {
        "run_id": summary.get("run_id"),
        "path": str(Path(path)),
        "status": summary.get("status"),
        "health": health.get("health"),
        "trustworthy": health.get("trustworthy"),
        "changed_paths": changed_paths,
        "validation_failed": bool(summary.get("validation_failed")),
        "last_validation_summary": validation_summary,
        "failed_tools": failed_tools,
        "issue_codes": issue_codes,
        "quality_gate": quality_gate,
        "quality_gate_checks": quality_gate_checks,
        "plan_snapshot": plan_snapshot,
        "next_action": next_action,
        "priority": priority,
        "resume_prompt": prompt,
    }


def build_latest_resume_context(runs_dir: str | Path | None = None) -> dict[str, Any] | None:
    path = latest_run_log(_runs_root(runs_dir))
    if path is None:
        return None
    return build_resume_context(path)


def build_resume_context_by_id(
    run_id: str, runs_dir: str | Path | None = None
) -> dict[str, Any] | None:
    path = find_run_log(run_id, _runs_root(runs_dir))
    if path is None:
        return None
    return build_resume_context(path)


def format_resume_context(context: dict[str, Any]) -> str:
    lines = [
        "Agent Task Resume",
        f"- run_id: {context.get('run_id') or 'unknown'}",
        f"- status: {context.get('status') or 'running/unknown'}",
        f"- health: {context.get('health') or 'unknown'}",
        f"- priority: {context.get('priority') or 'unknown'}",
    ]
    next_action = context.get("next_action")
    if isinstance(next_action, dict):
        lines.append(
            f"- next_action: {next_action.get('id') or 'unknown'}"
            f" ({next_action.get('status') or 'unknown'})"
        )
        if next_action.get("objective"):
            lines.append(f"- objective: {next_action['objective']}")
    changed_paths = context.get("changed_paths") if isinstance(context.get("changed_paths"), list) else []
    if changed_paths:
        lines.append("- changed_paths: " + ", ".join(str(path) for path in changed_paths))
    if context.get("last_validation_summary"):
        lines.append(f"- validation: {context['last_validation_summary']}")
    issues = context.get("issue_codes") if isinstance(context.get("issue_codes"), list) else []
    if issues:
        lines.append("- issues: " + ", ".join(str(item) for item in issues))
    quality_gate = context.get("quality_gate") if isinstance(context.get("quality_gate"), dict) else {}
    if quality_gate:
        lines.append(
            f"- quality_gate: {quality_gate.get('status') or 'unknown'}"
            f" ({quality_gate.get('summary') or 'no summary'})"
        )
    lines.append("")
    lines.append(str(context.get("resume_prompt") or "No resume prompt available."))
    return "\n".join(lines)


def _plan_snapshot(events: list[dict[str, Any]], finish_data: dict[str, Any]) -> dict[str, Any]:
    snapshot = finish_data.get("plan_snapshot")
    if isinstance(snapshot, dict):
        return snapshot
    plan = finish_data.get("plan")
    if isinstance(plan, list):
        return _snapshot_from_steps(plan)
    for event in reversed(events):
        data = _event_data(event)
        if event.get("event") != "agent_plan":
            continue
        plan = data.get("plan")
        if isinstance(plan, list):
            return _snapshot_from_steps(plan)
    return {"total": 0, "counts": {}, "next_action": None, "steps": []}


def _snapshot_from_steps(steps: list[Any]) -> dict[str, Any]:
    normalized = [step for step in steps if isinstance(step, dict)]
    counts: dict[str, int] = {}
    next_action = None
    for step in normalized:
        status = str(step.get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
        if next_action is None and status in {"active", "pending", "failed"}:
            next_action = step
    return {
        "total": len(normalized),
        "counts": counts,
        "next_action": next_action,
        "steps": normalized,
    }


def _next_action(plan_snapshot: dict[str, Any]) -> dict[str, Any] | None:
    next_action = plan_snapshot.get("next_action")
    if isinstance(next_action, dict):
        return next_action
    steps = plan_snapshot.get("steps")
    if not isinstance(steps, list):
        return None
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("status") or "") in {"active", "pending", "failed"}:
            return step
    return None


def _resume_priority(
    *,
    status: str,
    next_action: dict[str, Any] | None,
    changed_paths: list[str],
    validation_failed: bool,
    failed_tools: list[Any],
    issue_codes: list[str],
    quality_gate: dict[str, Any],
) -> str:
    next_id = str((next_action or {}).get("id") or "")
    if "validation_failed" in issue_codes or validation_failed:
        return "fix_validation_failure"
    if "unverified_changes" in issue_codes or (changed_paths and next_id == "validate_changes"):
        return "run_validation"
    if failed_tools:
        return "recover_failed_tool"
    if str(quality_gate.get("status") or "") == "fail":
        return "resolve_quality_gate_failure"
    if status and status != "completed":
        return "continue_incomplete_plan"
    if str(quality_gate.get("status") or "") == "warn":
        return "review_quality_gate_warnings"
    if next_action and next_id != "final_answer":
        return "continue_next_plan_step"
    return "summarize_or_confirm_done"


def _resume_prompt(
    *,
    summary: dict[str, Any],
    health: dict[str, Any],
    priority: str,
    next_action: dict[str, Any] | None,
    changed_paths: list[str],
    validation_summary: Any,
    failed_tools: list[Any],
    issue_codes: list[str],
    quality_gate: dict[str, Any],
    quality_gate_checks: list[dict[str, str]],
) -> str:
    lines = [
        "Resume the previous Agent task from the latest reliable checkpoint.",
        f"Run status: {summary.get('status') or 'running/unknown'}; health: {health.get('health') or 'unknown'}.",
        f"Resume priority: {priority}.",
    ]
    if next_action:
        lines.append(
            f"Next plan step: {next_action.get('id') or 'unknown'}"
            f" ({next_action.get('status') or 'unknown'}): {next_action.get('title') or ''}."
        )
        if next_action.get("objective"):
            lines.append(f"Objective: {next_action['objective']}")
    if changed_paths:
        lines.append("Changed paths to consider: " + ", ".join(changed_paths[:12]) + ".")
    if validation_summary:
        lines.append(f"Last validation summary: {validation_summary}.")
    if failed_tools:
        names = ", ".join(str(item.get("name") or "unknown") for item in failed_tools if isinstance(item, dict))
        if names:
            lines.append(f"Failed tools to inspect first: {names}.")
    if issue_codes:
        lines.append("Known issue codes: " + ", ".join(issue_codes) + ".")
    if quality_gate:
        lines.append(
            f"Quality gate: {quality_gate.get('status') or 'unknown'}; "
            f"{quality_gate.get('summary') or 'no summary'}."
        )
    if quality_gate_checks:
        lines.append(
            "Quality gate checks to address: "
            + "; ".join(
                f"{item.get('status')}:{item.get('code')} - {item.get('message')}"
                for item in quality_gate_checks[:5]
            )
            + "."
        )
    lines.append(_priority_instruction(priority))
    return "\n".join(lines)


def _priority_instruction(priority: str) -> str:
    if priority == "fix_validation_failure":
        return "Start by inspecting the validation failure, fix the real cause, then rerun focused validation."
    if priority == "run_validation":
        return "Start by validating the changed files before making new edits."
    if priority == "recover_failed_tool":
        return "Start by reviewing the failed tool output and choose a safer or narrower strategy."
    if priority == "resolve_quality_gate_failure":
        return "Start by resolving the failing quality gate check before making unrelated edits."
    if priority == "continue_incomplete_plan":
        return "Continue from the next unfinished plan step instead of restarting from scratch."
    if priority == "review_quality_gate_warnings":
        return "Start by reviewing the quality gate warnings and decide whether to fix or explicitly document them."
    if priority == "continue_next_plan_step":
        return "Continue the next pending plan step and keep the existing changed files in mind."
    return "Confirm whether any remaining work exists; if not, summarize the completed work and validation."


def _quality_gate_checks(quality_gate: dict[str, Any]) -> list[dict[str, str]]:
    checks = quality_gate.get("checks") if isinstance(quality_gate.get("checks"), list) else []
    selected: list[dict[str, str]] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status") or "")
        if status not in {"fail", "warn"}:
            continue
        selected.append(
            {
                "code": str(check.get("code") or "unknown"),
                "status": status,
                "message": str(check.get("message") or ""),
            }
        )
    return selected[:8]


def _last_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    return next((event for event in reversed(events) if event.get("event") == event_type), None)


def _event_data(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {}
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _runs_root(runs_dir: str | Path | None) -> Path:
    return Path(runs_dir) if runs_dir is not None else Path(STATE_DIR) / "runs"
