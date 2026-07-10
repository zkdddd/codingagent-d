from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


PlanStatus = Literal["pending", "active", "done", "skipped", "failed"]


@dataclass
class PlanStep:
    step_id: str
    title: str
    status: PlanStatus = "pending"
    detail: str | None = None
    objective: str | None = None
    files: list[str] | None = None
    risks: list[str] | None = None
    validation: list[str] | None = None


def build_task_plan(
    user_task: str,
    *,
    requires_tools: bool,
    requires_code_edit: bool,
) -> list[PlanStep]:
    task_profile = _task_profile(user_task)
    steps = [
        PlanStep(
            "understand_task",
            "Understand the user request",
            "done",
            objective="Clarify the requested outcome and decide whether tools or code edits are needed.",
            files=task_profile["files"],
            risks=task_profile["risks"],
        ),
    ]
    if requires_tools:
        steps.append(
            PlanStep(
                "inspect_context",
                "Inspect relevant project context",
                "active",
                objective="Read the smallest useful set of files before changing behavior.",
                files=task_profile["files"],
                risks=["stale assumptions", "missing related files"],
            )
        )
    if requires_code_edit:
        steps.append(
            PlanStep(
                "make_changes",
                "Make the required workspace changes",
                objective="Apply focused, reviewable edits that satisfy the requested feature or fix.",
                files=task_profile["files"],
                risks=_dedupe([*task_profile["risks"], "behavior regression", "over-broad edits"]),
            )
        )
        steps.append(
            PlanStep(
                "validate_changes",
                "Validate changed code",
                objective="Run the narrowest relevant checks first, then broader project validation when useful.",
                files=task_profile["files"],
                risks=["unverified changes", "false confidence from partial tests"],
                validation=task_profile["validation"],
            )
        )
    steps.append(
        PlanStep(
            "final_answer",
            "Summarize outcome for the user",
            objective="Report what changed, validation status, and any remaining risks clearly.",
            validation=task_profile["validation"],
        )
    )

    if not requires_tools and len(steps) > 1:
        steps[1].status = "active"
    return steps


def set_plan_step(
    steps: list[PlanStep],
    step_id: str,
    status: PlanStatus,
    detail: str | None = None,
) -> bool:
    for step in steps:
        if step.step_id != step_id:
            continue
        changed = step.status != status or step.detail != detail
        step.status = status
        if detail is not None or changed:
            step.detail = detail
        return changed
    return False


def plan_to_dicts(steps: list[PlanStep]) -> list[dict[str, object]]:
    return [
        {
            "id": step.step_id,
            "title": step.title,
            "status": step.status,
            "detail": step.detail,
            "objective": step.objective,
            "files": step.files or [],
            "risks": step.risks or [],
            "validation": step.validation or [],
        }
        for step in steps
    ]


def plan_for_model(steps: list[PlanStep]) -> str:
    lines = ["Execution checklist:"]
    for step in steps:
        detail = f" - {step.detail}" if step.detail else ""
        lines.append(f"- [{step.status}] {step.step_id}: {step.title}{detail}")
        if step.objective:
            lines.append(f"  objective: {step.objective}")
        if step.files:
            lines.append("  files: " + ", ".join(step.files[:8]))
        if step.risks:
            lines.append("  risks: " + ", ".join(step.risks[:5]))
        if step.validation:
            lines.append("  validation: " + ", ".join(step.validation[:5]))
    lines.append(
        "Use this checklist to stay on track. Update your behavior based on completed, failed, or pending steps."
    )
    return "\n".join(lines)


def plan_summary_text(steps: list[PlanStep]) -> str:
    return "; ".join(f"{step.step_id}={step.status}" for step in steps)


def next_plan_action(steps: list[PlanStep]) -> dict[str, object] | None:
    for step in steps:
        if step.status in {"active", "pending", "failed"}:
            return {
                "id": step.step_id,
                "title": step.title,
                "status": step.status,
                "objective": step.objective,
                "files": step.files or [],
                "risks": step.risks or [],
                "validation": step.validation or [],
            }
    return None


def plan_progress_snapshot(steps: list[PlanStep]) -> dict[str, object]:
    counts = {status: 0 for status in ("pending", "active", "done", "skipped", "failed")}
    for step in steps:
        counts[step.status] += 1
    return {
        "total": len(steps),
        "counts": counts,
        "next_action": next_plan_action(steps),
        "steps": plan_to_dicts(steps),
    }


def _task_profile(user_task: str) -> dict[str, list[str]]:
    text = str(user_task or "")
    files = _mentioned_files(text)
    lower = text.lower()
    risks: list[str] = []
    validation: list[str] = []
    if _contains_any(lower, ["删除", "remove", "delete", "回滚", "rollback"]):
        risks.append("destructive or rollback-sensitive change")
    if _contains_any(lower, ["ui", "界面", "按钮", "窗口", "前端"]):
        risks.append("UI behavior regression")
    if _contains_any(lower, ["上下文", "context", "记忆", "memory"]):
        risks.append("context or memory regression")
    if _contains_any(lower, ["验证", "测试", "test", "pytest", "命令"]):
        validation.append("run focused tests or learned validation commands")
    if _contains_any(
        lower,
        [
            "代码",
            "功能",
            "bug",
            "修复",
            "实现",
            "添加",
            "优化",
            "coding",
            "update",
            "change",
            "implement",
            "add",
            "optimize",
            "fix",
        ],
    ):
        validation.append("run related tests before full validation")
    if not validation:
        validation.append("validate when files are changed")
    return {
        "files": files,
        "risks": list(dict.fromkeys(risks)),
        "validation": list(dict.fromkeys(validation)),
    }


def _mentioned_files(text: str) -> list[str]:
    candidates = re.findall(
        r"(?<![\w.-])(?:[\w.-]+[\\/])+[\w.-]+\.[A-Za-z0-9_]+|(?<![\w.-])[\w.-]+\.(?:py|js|jsx|ts|tsx|go|rs|java|md|toml|json|yaml|yml|bat|ps1)",
        text,
    )
    normalized = [item.replace("\\", "/") for item in candidates]
    return list(dict.fromkeys(normalized))[:12]


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
