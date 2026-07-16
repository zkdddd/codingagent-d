from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from ..config import (
    AGENT_SYSTEM_PROMPT,
    APP_LANGUAGE,
    CONTEXT_KEEP_RECENT_MESSAGES,
    CONTEXT_MAX_TOKENS,
    CONTEXT_PER_MESSAGE_MAX_CHARS,
    CONTEXT_SUMMARY_MAX_CHARS,
    FILESYSTEM_COMMAND_SCOPE,
    FILESYSTEM_READ_SCOPE,
    FILESYSTEM_WRITE_SCOPE,
    MODEL,
    REASONING_EFFORT,
    normalize_reasoning_effort,
)
from ..context import manage_context
from ..llm import (
    AGENT_REQUEST_TIMEOUT_SECONDS,
    create_chat_completion_with_reasoning,
    runtime_metadata_prompt,
)
from .agent_stream import AggregatedAssistantMessage, aggregate_chat_completion_stream
from .change_plan import build_change_plan
from .failure_diagnostics import extract_failure_diagnostics
from .failure_focus import focus_prompt, focus_targets_from_diagnostics
from .final_trust import build_final_trust_summary, final_trust_prompt
from .risk_policy import tool_policy
from .patch_recovery import patch_failure_recovery, patch_recovery_prompt
from .project_memory import format_project_memory_for_prompt, load_or_refresh_project_memory
from .run_log import RunLogger
from .symbol_index import find_symbols
from .task_plan import (
    PlanStatus,
    PlanStep,
    build_task_plan,
    plan_for_model,
    plan_progress_snapshot,
    plan_summary_text,
    plan_to_dicts,
    set_plan_step,
)
from .tool_schema import tool_schema
from .tool_loop_guard import loop_warning_prompt, record_tool_call
from .tool_result_context import tool_result_json_for_model
from .tool_view import tool_display_args, tool_preview_text, tool_report_section
from .validation import (
    build_focused_validation_commands,
    build_validation_plan,
    validation_result_summary,
    validation_failure_prompt,
    validation_prompt,
)
from .workspace import WorkspaceError, WorkspaceTools

EmitFn = Callable[[str], None]
EventFn = Callable[[dict[str, Any]], None]
StopFn = Callable[[], bool]
ConfirmFn = Callable[[str, str, dict[str, Any], str | None, int | None, dict[str, Any]], bool]


class AgentPhase(str, Enum):
    STARTING = "starting"
    INSPECTING = "inspecting"
    PLANNING = "planning"
    EDITING = "editing"
    VALIDATING = "validating"
    REPAIRING = "repairing"
    FINALIZING = "finalizing"
    STOPPED = "stopped"


PHASE_STATUS_LABELS = {
    AgentPhase.STARTING: "Starting",
    AgentPhase.INSPECTING: "Inspecting project",
    AgentPhase.PLANNING: "Planning next step",
    AgentPhase.EDITING: "Editing files",
    AgentPhase.VALIDATING: "Running validation",
    AgentPhase.REPAIRING: "Repairing failed validation",
    AgentPhase.FINALIZING: "Preparing final answer",
    AgentPhase.STOPPED: "Stopped",
}


@dataclass
class AgentRunState:
    phase: AgentPhase = AgentPhase.STARTING
    inspected: bool = False
    mutated: bool = False
    content_changed: bool = False
    validated: bool = False
    validation_failed: bool = False
    changed_paths: set[str] | None = None
    last_validation_summary: str | None = None
    plan: list[PlanStep] | None = None
    focused_validation_commands: list[dict[str, Any]] | None = None
    tool_call_history: list[dict[str, Any]] | None = None
    failed_tool_count: int = 0
    loop_warning_count: int = 0

    def __post_init__(self) -> None:
        if self.changed_paths is None:
            self.changed_paths = set()
        if self.plan is None:
            self.plan = []
        if self.focused_validation_commands is None:
            self.focused_validation_commands = []
        if self.tool_call_history is None:
            self.tool_call_history = []

AGENT_WORKFLOW_HINT = """
Use the workspace tools in this order when it helps:
1. list_files to inspect the project tree.
2. search_file to locate symbols, files, or text.
3. read_file for focused excerpts.
4. make_directory when a target folder does not exist yet.
5. rename_path or copy_path when the task is moving, renaming, or duplicating files.
6. delete_path only when removal is explicitly required.
7. apply_patch for targeted edits when possible.
8. write_file only when a full replacement is simpler.
9. run_command to validate after edits.
10. list_rollback_history when the user asks what can be undone.
11. preview_rollback_change, preview_rollback_session, or preview_rollback_paths when the user wants to inspect rollback diffs before applying them.
12. rollback_last_change, rollback_change, or rollback_paths when the user explicitly asks to undo workspace changes in this chat session.

Prefer small, reviewable changes. If a command fails, inspect the output and fix the real cause before continuing.
If the task requires checking files, changing files, renaming paths, or running commands, do not stop after saying what you will do. In the same turn, call the next tool and continue the task.
Prefer low-risk read and validation steps first. Avoid destructive commands or broad file changes unless they are clearly needed for the user's request.
"""


def _normalize_display_text(text: str) -> str:
    return (
        text.replace("\u6d60\u8bf2\u59df", "任务")
        .replace("\u5bb8\u30e4\u7d94\u9356\u7bedn\n", "工作区\n\n")
        .replace("\u5bb8\u8e6d\u8151\u59dd\ue542n", "已中止\n")
        .replace("\u7f01\u64b4\u7049", "结果")
        .replace("\u5bb8\u30e5\u53ff\u748b\u51aa\u6564", "工具调用")
    )



class CodeAgent:
    INSPECTION_TOOLS = {
        "list_files",
        "search_file",
        "find_symbol",
        "suggest_self_improvements",
        "read_file",
        "list_rollback_history",
        "preview_rollback_change",
        "preview_rollback_session",
        "preview_rollback_paths",
    }
    CONTENT_EDIT_TOOLS = {
        "write_file",
        "apply_patch",
        "rollback_last_change",
        "rollback_change",
        "rollback_paths",
    }
    MUTATION_TOOLS = {
        "write_file",
        "apply_patch",
        "rename_path",
        "copy_path",
        "delete_path",
        "make_directory",
        "rollback_last_change",
        "rollback_change",
        "rollback_paths",
    }
    VALIDATION_TOOLS = {"run_command"}
    MAX_VALIDATION_REPAIR_ROUNDS = 3

    def __init__(
        self,
        workspace_root: str | None = None,
        model: str = MODEL,
        reasoning_effort: str = REASONING_EFFORT,
        confirm_tool: ConfirmFn | None = None,
        session_id: str | None = None,
    ):
        self.workspace = (
            WorkspaceTools(workspace_root, session_id=session_id)
            if workspace_root
            else WorkspaceTools(session_id=session_id)
        )
        self.model = model
        self.reasoning_effort = normalize_reasoning_effort(reasoning_effort)
        self.confirm_tool = confirm_tool
        self.session_id = session_id
        self.run_logger: RunLogger | None = None
        self._run_log_finished = False
        self._context_compaction_notified = False

    def _prepare_model_messages(
        self,
        messages: list[dict[str, Any]],
        on_event: EventFn | None,
    ) -> list[dict[str, Any]]:
        managed, stats = manage_context(
            messages,
            max_tokens=CONTEXT_MAX_TOKENS,
            keep_recent_messages=CONTEXT_KEEP_RECENT_MESSAGES,
            summary_max_chars=CONTEXT_SUMMARY_MAX_CHARS,
            per_message_max_chars=CONTEXT_PER_MESSAGE_MAX_CHARS,
        )
        if stats.compacted:
            messages[:] = managed
            if not self._context_compaction_notified:
                self._context_compaction_notified = True
                self._emit_event(
                    on_event,
                    {
                        "type": "agent_status",
                        "status": (
                            "Context compacted "
                            f"({stats.original_tokens} -> {stats.final_tokens} estimated tokens)"
                        ),
                        "kind": "active",
                    },
                )
        return managed

    @staticmethod
    def _task_requires_tools(user_task: str) -> bool:
        text = (user_task or "").strip().lower()
        if not text:
            return False

        keywords = (
            "read",
            "open",
            "check",
            "inspect",
            "search",
            "find",
            "edit",
            "modify",
            "change",
            "rename",
            "move",
            "copy",
            "delete",
            "mkdir",
            "create",
            "write",
            "run",
            "command",
            "file",
            "folder",
            "directory",
            "读取",
            "查看",
            "检查",
            "搜索",
            "修改",
            "重命名",
            "移动",
            "复制",
            "删除",
            "新建",
            "创建",
            "目录创建",
            "写入",
            "执行",
            "运行",
            "文件",
            "文件夹",
            "目录",
            ".py",
            ".cpp",
            ".h",
            ".hpp",
            ".md",
            ".txt",
            ":\\",
            "/",
        )
        extra_keywords = (
            "rollback",
            "undo",
            "revert",
            "\u56de\u6eda",
            "\u64a4\u9500",
            "\u6062\u590d\u6539\u52a8",
        )
        return any(keyword in text for keyword in keywords + extra_keywords)

    @staticmethod
    def _task_requires_code_edit(user_task: str) -> bool:
        text = (user_task or "").strip().lower()
        if not text:
            return False

        keywords = (
            "fix",
            "bug",
            "implement",
            "feature",
            "refactor",
            "update",
            "edit",
            "modify",
            "change code",
            "patch",
            "修复",
            "报错",
            "实现",
            "功能",
            "重构",
            "更新",
            "改代码",
            "修改代码",
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".java",
            ".go",
            ".rs",
        )
        return any(keyword in text for keyword in keywords)

    @classmethod
    def _tool_result_ok(cls, name: str, result: dict[str, Any]) -> bool:
        if not isinstance(result, dict):
            return False
        if result.get("rejected"):
            return False
        if "ok" in result and not bool(result.get("ok")):
            return False
        if name == "run_command":
            if bool(result.get("timed_out", False)):
                return False
            return int(result.get("returncode", 0) or 0) == 0
        return "error" not in result

    @classmethod
    def _paths_touched_by_tool(cls, name: str, result: dict[str, Any]) -> list[str]:
        if not isinstance(result, dict):
            return []
        if name == "apply_patch":
            return [str(path) for path in result.get("files_touched", [])]
        if name == "write_file":
            return [str(result["path"])] if result.get("path") else []
        if name in {"rollback_last_change", "rollback_change", "rollback_paths"}:
            return [str(path) for path in result.get("paths", [])]
        if name == "rename_path":
            paths: list[str] = []
            if result.get("source_path"):
                paths.append(str(result["source_path"]))
            if result.get("target_path"):
                paths.append(str(result["target_path"]))
            return paths
        if name == "copy_path":
            paths = []
            if result.get("source_path"):
                paths.append(str(result["source_path"]))
            if result.get("target_path"):
                paths.append(str(result["target_path"]))
            return paths
        if name in {"delete_path", "make_directory"}:
            return [str(result["path"])] if result.get("path") else []
        return []

    def _emit(self, emit: EmitFn | None, parts: list[str], text: str) -> None:
        text = _normalize_display_text(text)
        parts.append(text)
        if emit:
            emit(text)

    def _stream_assistant_message(
        self,
        request_messages: list[dict[str, Any]],
        emit: EmitFn | None,
        report_parts: list[str],
    ) -> tuple[AggregatedAssistantMessage, bool]:
        stream_started = False

        def on_text_delta(delta: str) -> None:
            nonlocal stream_started
            if not stream_started:
                stream_started = True
                self._emit(emit, report_parts, "### 模型输出\n\n")
            self._emit(emit, report_parts, delta)

        stream = create_chat_completion_with_reasoning(
            model=self.model,
            messages=request_messages,
            tools=tool_schema(),
            tool_choice="auto",
            temperature=0.2,
            timeout=AGENT_REQUEST_TIMEOUT_SECONDS,
            stream=True,
            reasoning_effort=self.reasoning_effort,
            on_request_event=self._write_model_request_event,
        )
        try:
            return (
                aggregate_chat_completion_stream(stream, on_text_delta=on_text_delta),
                stream_started,
            )
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()

    def _emit_event(self, on_event: EventFn | None, event: dict[str, Any]) -> None:
        if self.run_logger is not None:
            self.run_logger.write(str(event.get("type") or "event"), event)
        if on_event:
            on_event(event)

    def _write_model_request_event(self, event: dict[str, Any]) -> None:
        if self.run_logger is None:
            return
        event_type = str(event.get("type") or "model_event")
        payload = {key: value for key, value in event.items() if key != "type"}
        self.run_logger.write(event_type, payload)

    def _finish_run_log(self, status: str, data: dict[str, Any] | None = None) -> None:
        if self.run_logger is None or self._run_log_finished:
            return
        self._run_log_finished = True
        self.run_logger.finish(status, data)

    def _finish_run_with_trust_check(
        self,
        status: str,
        state: AgentRunState,
        on_event: EventFn | None,
    ) -> None:
        trust_summary = self._final_trust_summary(state, status=status)
        self._emit_event(
            on_event,
            {
                "type": "final_trust_check",
                "trust": trust_summary,
            },
        )
        payload = self._run_state_payload(state)
        payload["final_trust"] = trust_summary
        self._finish_run_log(status, payload)

    @staticmethod
    def _run_state_payload(state: AgentRunState) -> dict[str, Any]:
        return {
            "phase": state.phase.value,
            "inspected": state.inspected,
            "mutated": state.mutated,
            "content_changed": state.content_changed,
            "validated": state.validated,
            "validation_failed": state.validation_failed,
            "changed_paths": sorted(state.changed_paths or []),
            "last_validation_summary": state.last_validation_summary,
            "plan": plan_to_dicts(state.plan or []),
            "plan_snapshot": plan_progress_snapshot(state.plan or []),
            "focused_validation_commands": state.focused_validation_commands or [],
            "tool_call_history": state.tool_call_history or [],
        }

    def _record_tool_loop_guard(
        self,
        state: AgentRunState,
        *,
        name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        ok: bool,
        messages: list[dict[str, Any]],
        on_event: EventFn | None,
        round_idx: int,
    ) -> None:
        history = state.tool_call_history if state.tool_call_history is not None else []
        state.tool_call_history = history
        warning = record_tool_call(
            history,
            name=name,
            args=args,
            ok=ok,
            summary=str(
                result.get("summary")
                or result.get("error")
                or result.get("stderr")
                or result.get("stdout")
                or ""
            ).strip()[:500],
        )
        if not warning:
            return
        state.loop_warning_count += 1
        self._emit_event(
            on_event,
            {
                "type": "tool_loop_warning",
                "warning": warning,
                "round": round_idx,
            },
        )
        prompt = loop_warning_prompt(warning)
        if prompt:
            messages.append({"role": "system", "content": prompt})

    def _set_plan_step(
        self,
        state: AgentRunState,
        step_id: str,
        status: PlanStatus,
        on_event: EventFn | None,
        *,
        detail: str | None = None,
        force: bool = False,
    ) -> None:
        changed = set_plan_step(state.plan or [], step_id, status, detail)
        if not changed and not force:
            return
        self._emit_event(
            on_event,
            {
                "type": "agent_plan",
                "step_id": step_id,
                "status": status,
                "detail": detail,
                "plan": plan_to_dicts(state.plan or []),
            },
        )

    def _set_plan_for_tool(
        self,
        state: AgentRunState,
        name: str,
        status: PlanStatus,
        on_event: EventFn | None,
        *,
        detail: str | None = None,
    ) -> None:
        if name in self.INSPECTION_TOOLS:
            self._set_plan_step(state, "inspect_context", status, on_event, detail=detail)
        elif name in self.MUTATION_TOOLS:
            self._set_plan_step(state, "make_changes", status, on_event, detail=detail)
        elif name in self.VALIDATION_TOOLS:
            self._set_plan_step(state, "validate_changes", status, on_event, detail=detail)

    def _set_phase(
        self,
        state: AgentRunState,
        phase: AgentPhase,
        on_event: EventFn | None,
        *,
        detail: str | None = None,
        force: bool = False,
    ) -> None:
        if state.phase == phase and not force:
            return
        state.phase = phase
        event: dict[str, Any] = {
            "type": "agent_status",
            "phase": phase.value,
            "status": PHASE_STATUS_LABELS[phase],
            "kind": "active",
        }
        if detail:
            event["detail"] = detail
        self._emit_event(on_event, event)

    def _final_trust_summary(self, state: AgentRunState, *, status: str) -> dict[str, Any]:
        return build_final_trust_summary(
            status=status,
            content_changed=state.content_changed,
            changed_paths=sorted(state.changed_paths or []),
            validated=state.validated,
            validation_failed=state.validation_failed,
            last_validation_summary=state.last_validation_summary,
            failed_tool_count=state.failed_tool_count,
            loop_warning_count=state.loop_warning_count,
        )

    def _final_response_prompt(self, state: AgentRunState) -> str:
        changed_paths = sorted(state.changed_paths or [])
        changed_text = ", ".join(changed_paths[:12]) if changed_paths else "none"
        validation_status = "not run"
        if state.validated:
            validation_status = "failed" if state.validation_failed else "passed"
        summary = state.last_validation_summary or "none"
        trust_summary = self._final_trust_summary(state, status="completed")
        return (
            "Prepare the final user-facing answer from the actual execution state.\n"
            f"- inspected_project: {state.inspected}\n"
            f"- mutated_workspace: {state.mutated}\n"
            f"- content_changed: {state.content_changed}\n"
            f"- changed_paths: {changed_text}\n"
            f"- validation_status: {validation_status}\n"
            f"- last_validation_summary: {summary}\n"
            f"- plan_status: {plan_summary_text(state.plan or [])}\n\n"
            f"{final_trust_prompt(trust_summary)}\n\n"
            "Keep it concise. State what changed, what validation ran, and any remaining risk. "
            "Do not claim validation passed if validation_status is not passed."
        )

    @staticmethod
    def _append_synthetic_tool_call(
        messages: list[dict[str, Any]],
        call_id: str,
        name: str,
        args: dict[str, Any],
    ) -> None:
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }
                ],
            }
        )

    def _execute_tool_action(
        self,
        *,
        call_id: str,
        name: str,
        args: dict[str, Any],
        round_idx: int,
        messages: list[dict[str, Any]],
        report_parts: list[str],
        emit: EmitFn | None,
        on_event: EventFn | None,
        append_assistant_stub: bool = False,
    ) -> tuple[dict[str, Any], bool, dict[str, Any], str | None]:
        if append_assistant_stub:
            self._append_synthetic_tool_call(messages, call_id, name, args)

        display_args = tool_display_args(self.workspace, name, args)
        preview_text = tool_preview_text(self.workspace, name, args)
        policy = tool_policy(name, args, display_args, preview_text)
        change_plan = build_change_plan(
            name,
            display_args,
            preview=preview_text,
            policy=policy,
        )
        self._emit_event(
            on_event,
            {
                "type": "tool_start",
                "call_id": call_id,
                "name": name,
                "args": display_args,
                "policy": policy,
                "round": round_idx,
            },
        )
        if preview_text:
            self._emit_event(
                on_event,
                {
                    "type": "tool_preview",
                    "call_id": call_id,
                    "name": name,
                    "args": display_args,
                    "preview": preview_text,
                    "policy": policy,
                    "round": round_idx,
                },
            )
        if change_plan:
            self._emit_event(
                on_event,
                {
                    "type": "change_plan",
                    "call_id": call_id,
                    "name": name,
                    "plan": change_plan,
                    "round": round_idx,
                },
            )

        approved = True
        if bool(policy.get("approval_required")) and self.confirm_tool is not None:
            approved = bool(
                self.confirm_tool(
                    call_id,
                    name,
                    display_args,
                    preview_text,
                    round_idx,
                    policy,
                )
            )

        if not approved:
            result = {
                "ok": False,
                "error": f"Action rejected by user approval gate ({policy.get('risk_label', 'Risk review')}).",
                "rejected": True,
            }
        else:
            try:
                result = self._dispatch_tool(name, args)
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}

        result_ok = self._tool_result_ok(name, result)
        if change_plan:
            result = dict(result)
            result["change_plan"] = change_plan
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": tool_result_json_for_model(name, result),
            }
        )
        self._emit_event(
            on_event,
            {
                "type": "tool_result",
                "call_id": call_id,
                "name": name,
                "args": display_args,
                "result": result,
                "policy": policy,
                "round": round_idx,
                "ok": result_ok,
            },
        )
        self._emit(
            emit,
            report_parts,
            tool_report_section(
                name,
                display_args,
                result,
                preview=preview_text,
                policy=policy,
                change_plan=change_plan,
            ),
        )
        if name == "apply_patch" and not result_ok:
            self._recover_failed_patch(
                result=result,
                change_plan=change_plan,
                call_id=call_id,
                round_idx=round_idx,
                messages=messages,
                report_parts=report_parts,
                emit=emit,
                on_event=on_event,
            )
        return result, result_ok, display_args, preview_text

    def _recover_failed_patch(
        self,
        *,
        result: dict[str, Any],
        change_plan: dict[str, Any] | None,
        call_id: str,
        round_idx: int,
        messages: list[dict[str, Any]],
        report_parts: list[str],
        emit: EmitFn | None,
        on_event: EventFn | None,
    ) -> None:
        recovery = patch_failure_recovery(result, change_plan=change_plan)
        if not recovery:
            return
        targets = recovery.get("read_targets") if isinstance(recovery.get("read_targets"), list) else []
        self._emit_event(
            on_event,
            {
                "type": "patch_recovery",
                "call_id": call_id,
                "recovery": recovery,
                "round": round_idx,
            },
        )
        for idx, target in enumerate(targets, start=1):
            if not isinstance(target, dict) or not target.get("path"):
                continue
            args = {
                "path": str(target["path"]),
                "start_line": int(target.get("start_line") or 1),
                "end_line": int(target.get("end_line") or 220),
                "max_chars": int(target.get("max_chars") or 20000),
            }
            self._execute_tool_action(
                call_id=f"{call_id}-patch-recovery-{idx}",
                name="read_file",
                args=args,
                round_idx=round_idx,
                messages=messages,
                report_parts=report_parts,
                emit=emit,
                on_event=on_event,
                append_assistant_stub=True,
            )
        prompt = patch_recovery_prompt(recovery)
        if prompt:
            messages.append({"role": "system", "content": prompt})

    def _emit_validation_plan(
        self,
        *,
        call_id: str,
        plan: dict[str, Any],
        changed_paths: set[str],
        round_idx: int,
        report_parts: list[str],
        emit: EmitFn | None,
        on_event: EventFn | None,
    ) -> None:
        args = {"changed_paths": sorted(changed_paths)[:12]}
        result = {
            "summary": str(plan.get("summary") or "").strip(),
            "project_type": plan.get("project_type"),
            "command_count": int(plan.get("command_count") or 0),
            "commands": plan.get("commands") if isinstance(plan.get("commands"), list) else [],
            "changed_paths": plan.get("changed_paths") if isinstance(plan.get("changed_paths"), list) else [],
        }
        self._emit_event(
            on_event,
            {
                "type": "tool_result",
                "call_id": call_id,
                "name": "validation_plan",
                "args": args,
                "result": result,
                "round": round_idx,
                "ok": True,
            },
        )
        self._emit(
            emit,
            report_parts,
            tool_report_section("validation_plan", args, result),
        )

    def _run_auto_validation(
        self,
        *,
        plan: dict[str, Any],
        validation_run_seq: int,
        round_idx: int,
        state: AgentRunState,
        messages: list[dict[str, Any]],
        report_parts: list[str],
        emit: EmitFn | None,
        on_event: EventFn | None,
    ) -> tuple[bool, str | None, int]:
        commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
        if not commands:
            return True, str(plan.get("summary") or "").strip() or None, 0

        self._set_phase(
            state,
            AgentPhase.VALIDATING,
            on_event,
        )

        last_summary: str | None = None
        executed = 0
        for idx, command_info in enumerate(commands, start=1):
            if not isinstance(command_info, dict):
                continue
            executed += 1
            call_id = f"validation-run-{validation_run_seq}-{idx}"
            args = {
                "command": str(command_info.get("command") or ""),
                "cwd": str(command_info.get("cwd") or "."),
                "timeout_ms": int(command_info.get("timeout_ms") or 120000),
            }
            result, result_ok, _, _ = self._execute_tool_action(
                call_id=call_id,
                name="run_command",
                args=args,
                round_idx=round_idx,
                messages=messages,
                report_parts=report_parts,
                emit=emit,
                on_event=on_event,
                append_assistant_stub=True,
            )
            self._record_tool_loop_guard(
                state,
                name="run_command",
                args=args,
                result=result,
                ok=result_ok,
                messages=messages,
                on_event=on_event,
                round_idx=round_idx,
            )
            last_summary = validation_result_summary(result, command_info)
            if not result_ok:
                diagnostics = extract_failure_diagnostics(result)
                state.focused_validation_commands = build_focused_validation_commands(
                    diagnostics,
                    base_command=command_info,
                )
                if state.focused_validation_commands:
                    self._emit_event(
                        on_event,
                        {
                            "type": "focused_validation_plan",
                            "commands": state.focused_validation_commands,
                            "round": round_idx,
                        },
                    )
                focus_targets = self._read_failure_focus(
                    result=result,
                    validation_run_seq=validation_run_seq,
                    command_idx=idx,
                    round_idx=round_idx,
                    state=state,
                    messages=messages,
                    report_parts=report_parts,
                    emit=emit,
                    on_event=on_event,
                )
                prompt = focus_prompt(focus_targets)
                if prompt:
                    messages.append({"role": "system", "content": prompt})
                self._set_phase(
                    state,
                    AgentPhase.REPAIRING,
                    on_event,
                )
                return False, last_summary, executed

        self._set_phase(
            state,
            AgentPhase.VALIDATING,
            on_event,
            detail="Validation completed",
            force=True,
        )
        return True, last_summary, executed

    def _read_failure_focus(
        self,
        *,
        result: dict[str, Any],
        validation_run_seq: int,
        command_idx: int,
        round_idx: int,
        state: AgentRunState,
        messages: list[dict[str, Any]],
        report_parts: list[str],
        emit: EmitFn | None,
        on_event: EventFn | None,
    ) -> list[dict[str, Any]]:
        diagnostics = extract_failure_diagnostics(result)
        targets = focus_targets_from_diagnostics(diagnostics)
        if not targets:
            return []

        self._set_phase(
            state,
            AgentPhase.INSPECTING,
            on_event,
            detail="Reading focused failure locations",
            force=True,
        )
        self._set_plan_step(
            state,
            "inspect_context",
            "active",
            on_event,
            detail="Reading focused failure locations",
        )
        self._emit_event(
            on_event,
            {
                "type": "failure_focus",
                "diagnostics": diagnostics,
                "targets": targets,
                "round": round_idx,
            },
        )

        for idx, target in enumerate(targets, start=1):
            args = {
                "path": target["path"],
                "start_line": target["start_line"],
                "end_line": target["end_line"],
                "max_chars": target["max_chars"],
            }
            read_result, read_ok, _, _ = self._execute_tool_action(
                call_id=f"failure-focus-{validation_run_seq}-{command_idx}-{idx}",
                name="read_file",
                args=args,
                round_idx=round_idx,
                messages=messages,
                report_parts=report_parts,
                emit=emit,
                on_event=on_event,
                append_assistant_stub=True,
            )
            if read_ok:
                state.inspected = True
                self._set_plan_step(
                    state,
                    "inspect_context",
                    "done",
                    on_event,
                    detail=f"Read failure focus `{read_result.get('path', target['path'])}`",
                )
        return targets

    def _dispatch_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "list_files":
            return self.workspace.list_files(
                path=str(args.get("path", ".")),
                max_depth=args.get("max_depth", 3),
                include_dirs=bool(args.get("include_dirs", True)),
                include_hidden=bool(args.get("include_hidden", False)),
                max_results=int(args.get("max_results", 500)),
            )
        if name == "search_file":
            return self.workspace.search_file(
                query=str(args["query"]),
                path=str(args.get("path", ".")),
                file_glob=str(args.get("file_glob", "*")),
                case_sensitive=bool(args.get("case_sensitive", False)),
                include_hidden=bool(args.get("include_hidden", False)),
                context_lines=int(args.get("context_lines", 1)),
                max_results=int(args.get("max_results", 50)),
            )
        if name == "find_symbol":
            kind = args.get("kind")
            if kind is not None:
                kind = str(kind)
            return {
                "query": str(args["query"]),
                "kind": kind,
                "exact": bool(args.get("exact", True)),
                "matches": find_symbols(
                    self.workspace.root,
                    str(args["query"]),
                    kind=kind,
                    exact=bool(args.get("exact", True)),
                    limit=int(args.get("limit", 50)),
                ),
            }
        if name == "suggest_self_improvements":
            return self.workspace.suggest_self_improvements(
                limit=int(args.get("limit", 5)),
            )
        if name == "read_file":
            return self.workspace.read_file(
                path=str(args["path"]),
                start_line=args.get("start_line"),
                end_line=args.get("end_line"),
                max_chars=int(args.get("max_chars", 20000)),
            )
        if name == "write_file":
            return self.workspace.write_file(
                path=str(args["path"]),
                content=str(args["content"]),
            )
        if name == "rename_path":
            return self.workspace.rename_path(
                source_path=str(args["source_path"]),
                target_path=str(args["target_path"]),
            )
        if name == "copy_path":
            return self.workspace.copy_path(
                source_path=str(args["source_path"]),
                target_path=str(args["target_path"]),
            )
        if name == "delete_path":
            return self.workspace.delete_path(
                path=str(args["path"]),
                recursive=bool(args.get("recursive", True)),
            )
        if name == "make_directory":
            return self.workspace.make_directory(
                path=str(args["path"]),
            )
        if name == "apply_patch":
            return self.workspace.apply_patch(
                patch=str(args["patch"]),
            )
        if name == "run_command":
            return self.workspace.run_command(
                command=str(args["command"]),
                cwd=args.get("cwd"),
                timeout_ms=int(args.get("timeout_ms", 120000)),
            )
        if name == "list_rollback_history":
            return self.workspace.list_rollback_history(
                limit=int(args.get("limit", 12)),
                include_inactive=bool(args.get("include_inactive", True)),
            )
        if name == "preview_rollback_change":
            return self.workspace.preview_rollback_change(
                rollback_id=int(args["rollback_id"]),
            )
        if name == "preview_rollback_session":
            return self.workspace.preview_rollback_session(
                limit=int(args.get("limit", 50)),
            )
        if name == "preview_rollback_paths":
            return self.workspace.preview_rollback_paths(
                paths=[str(path) for path in args.get("paths", [])],
                rollback_id=args.get("rollback_id"),
            )
        if name == "rollback_last_change":
            return self.workspace.rollback_last_change()
        if name == "rollback_change":
            return self.workspace.rollback_change(
                rollback_id=int(args["rollback_id"]),
            )
        if name == "rollback_paths":
            return self.workspace.rollback_paths(
                paths=[str(path) for path in args.get("paths", [])],
                rollback_id=args.get("rollback_id"),
            )
        raise WorkspaceError(f"Unknown tool: {name}")

    def run(
        self,
        history: list[dict[str, Any]],
        emit: EmitFn | None = None,
        on_event: EventFn | None = None,
        should_stop: StopFn | None = None,
        max_rounds: int = 12,
    ) -> str:
        if not history:
            raise WorkspaceError("history is required")
        self.run_logger = RunLogger(self.session_id, str(self.workspace.root))
        self._run_log_finished = False

        user_task = ""
        for item in reversed(history):
            if item.get("role") == "user":
                user_task = str(item.get("content", ""))
                break

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    AGENT_SYSTEM_PROMPT.format(workspace_root=str(self.workspace.root))
                    + "\n\n"
                    + (
                        "Filesystem permissions:\n"
                        f"- read: {FILESYSTEM_READ_SCOPE}\n"
                        f"- write: {FILESYSTEM_WRITE_SCOPE}\n"
                        f"- command: {FILESYSTEM_COMMAND_SCOPE}\n"
                        f"Language: {'English' if APP_LANGUAGE == 'en' else 'Simplified Chinese'}\n"
                        "Use this language for user-facing status and final answers. "
                        "Use absolute paths only when the user's task clearly requires them. "
                        "Do not write, delete, rename, or run commands outside the allowed permission scope."
                    )
                    + "\n\n"
                    + runtime_metadata_prompt(self.model, self.reasoning_effort)
                    + "\n\n"
                    + AGENT_WORKFLOW_HINT
                ),
            }
        ]
        for item in history:
            if item.get("role") in ("system", "user", "assistant"):
                messages.append(
                    {
                        "role": item["role"],
                        "content": str(item.get("content", "")),
                    }
                )

        report_parts: list[str] = []
        tool_retry_forced = False
        require_tools = self._task_requires_tools(user_task)
        require_code_inspection = self._task_requires_code_edit(user_task)
        inspection_retry_forced = False
        validation_retry_forced = False
        final_response_forced = False
        validation_repair_attempts = 0
        validation_plan_run_seq = 0
        project_memory_prompt = ""
        try:
            project_memory = load_or_refresh_project_memory(self.workspace.root)
            project_memory_prompt = format_project_memory_for_prompt(project_memory)
        except Exception as exc:
            project_memory_prompt = f"Long-term project memory is unavailable: {exc}"
        state = AgentRunState(
            changed_paths=set(),
            plan=build_task_plan(
                user_task,
                requires_tools=require_tools,
                requires_code_edit=require_code_inspection,
            ),
        )
        if project_memory_prompt:
            messages.append({"role": "system", "content": project_memory_prompt})
        messages.append({"role": "system", "content": plan_for_model(state.plan or [])})
        validation_plan: dict[str, Any] | None = None
        validation_plan_announced = False
        self._emit_event(
            on_event,
            {
                "type": "agent_start",
                "task": user_task,
                "workspace_root": str(self.workspace.root),
                "run_id": self.run_logger.run_id if self.run_logger else None,
                "run_log_path": str(self.run_logger.path) if self.run_logger else None,
            },
        )
        self._emit_event(
            on_event,
            {
                "type": "agent_plan",
                "step_id": None,
                "status": "created",
                "plan": plan_to_dicts(state.plan or []),
            },
        )
        self._emit(
            emit,
            report_parts,
            "### 浠诲姟\n\n"
            f"{user_task}\n\n"
            f"### 宸ヤ綔鍖篭n\n`{self.workspace.root}`\n",
        )

        self._set_phase(state, AgentPhase.PLANNING, on_event)

        for round_idx in range(max_rounds):
            if should_stop and should_stop():
                self._set_phase(state, AgentPhase.STOPPED, on_event)
                self._emit(emit, report_parts, "\n> 宸蹭腑姝n")
                self._finish_run_with_trust_check("stopped", state, on_event)
                return "".join(report_parts)

            if state.content_changed and not state.validated:
                if validation_plan is None:
                    validation_plan = build_validation_plan(
                        changed_paths=state.changed_paths or set(),
                        workspace=self.workspace,
                    )
                if not validation_plan_announced:
                    validation_plan_run_seq += 1
                    self._emit_validation_plan(
                        call_id=f"validation-plan-{validation_plan_run_seq}",
                        plan=validation_plan,
                        changed_paths=state.changed_paths or set(),
                        round_idx=round_idx + 1,
                        report_parts=report_parts,
                        emit=emit,
                        on_event=on_event,
                    )
                    validation_plan_announced = True

                plan_commands = (
                    validation_plan.get("commands")
                    if isinstance(validation_plan.get("commands"), list)
                    else []
                )
                focused_commands = state.focused_validation_commands or []
                if focused_commands:
                    self._set_plan_step(
                        state,
                        "validate_changes",
                        "active",
                        on_event,
                        detail="Running focused validation before full validation",
                    )
                    validation_plan_run_seq += 1
                    ok, summary, executed = self._run_auto_validation(
                        plan={
                            "summary": "Run focused validation for the last failure before the full validation plan.",
                            "project_type": validation_plan.get("project_type", "focused"),
                            "commands": focused_commands,
                            "command_count": len(focused_commands),
                        },
                        validation_run_seq=validation_plan_run_seq,
                        round_idx=round_idx + 1,
                        state=state,
                        messages=messages,
                        report_parts=report_parts,
                        emit=emit,
                        on_event=on_event,
                    )
                    state.last_validation_summary = summary
                    if not ok:
                        state.validated = True
                        state.validation_failed = True
                        self._set_plan_step(
                            state,
                            "validate_changes",
                            "failed",
                            on_event,
                            detail=summary,
                        )
                    else:
                        state.focused_validation_commands = []
                        state.validated = False
                        state.validation_failed = False
                        self._set_plan_step(
                            state,
                            "validate_changes",
                            "active",
                            on_event,
                            detail="Focused validation passed; full validation still required",
                        )
                    if executed > 0:
                        validation_retry_forced = True
                    continue
                if plan_commands:
                    self._set_plan_step(
                        state,
                        "validate_changes",
                        "active",
                        on_event,
                        detail="Running automatic validation",
                    )
                    validation_plan_run_seq += 1
                    ok, summary, executed = self._run_auto_validation(
                        plan=validation_plan,
                        validation_run_seq=validation_plan_run_seq,
                        round_idx=round_idx + 1,
                        state=state,
                        messages=messages,
                        report_parts=report_parts,
                        emit=emit,
                        on_event=on_event,
                    )
                    state.validated = True
                    state.validation_failed = not ok
                    state.last_validation_summary = summary
                    if ok:
                        state.focused_validation_commands = []
                    self._set_plan_step(
                        state,
                        "validate_changes",
                        "done" if ok else "failed",
                        on_event,
                        detail=summary,
                    )
                    if executed > 0:
                        validation_retry_forced = True
                    continue

                state.validated = True
                state.validation_failed = False
                state.last_validation_summary = str(validation_plan.get("summary") or "").strip() or None
                self._set_plan_step(
                    state,
                    "validate_changes",
                    "skipped",
                    on_event,
                    detail=state.last_validation_summary,
                )
                messages.append(
                    {
                        "role": "system",
                        "content": validation_prompt(state.changed_paths or set(), validation_plan),
                    }
                )
                continue

            self._set_phase(state, AgentPhase.PLANNING, on_event)
            request_messages = self._prepare_model_messages(messages, on_event)
            assistant, assistant_text_streamed = self._stream_assistant_message(
                request_messages,
                emit,
                report_parts,
            )
            assistant_dump = assistant.model_dump(exclude_none=True)
            messages.append(assistant_dump)

            tool_calls = assistant.tool_calls or []
            assistant_text = (assistant.content or "").strip()

            if tool_calls:
                current_tool_names = [tool_call.function.name for tool_call in tool_calls]
                current_has_inspection = any(
                    name in self.INSPECTION_TOOLS for name in current_tool_names
                )
                current_has_content_edit = any(
                    name in self.CONTENT_EDIT_TOOLS for name in current_tool_names
                )
                if (
                    require_code_inspection
                    and not state.inspected
                    and current_has_content_edit
                    and not current_has_inspection
                    and not inspection_retry_forced
                ):
                    inspection_retry_forced = True
                    self._set_phase(
                        state,
                        AgentPhase.INSPECTING,
                        on_event,
                        detail="Inspection required before editing",
                    )
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Before editing code, inspect the relevant project structure and file contents first. "
                                "Use list_files, search_file, or read_file to gather context, then edit."
                            ),
                        }
                    )
                    if assistant_text and not assistant_text_streamed:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue

            if not tool_calls:
                if require_tools and not tool_retry_forced:
                    tool_retry_forced = True
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "The user asked for a workspace action. Do not stop after describing intent. "
                                "Call the appropriate tool now, or explicitly explain that the path is outside the workspace."
                            ),
                        }
                    )
                    if assistant_text and not assistant_text_streamed:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue
                if state.content_changed and not state.validated and not validation_retry_forced:
                    validation_retry_forced = True
                    messages.append(
                        {
                            "role": "system",
                            "content": validation_prompt(state.changed_paths or set(), validation_plan),
                        }
                    )
                    if assistant_text and not assistant_text_streamed:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue
                if (
                    state.content_changed
                    and state.validation_failed
                    and validation_repair_attempts < self.MAX_VALIDATION_REPAIR_ROUNDS
                ):
                    validation_repair_attempts += 1
                    self._set_phase(state, AgentPhase.REPAIRING, on_event)
                    self._set_plan_step(
                        state,
                        "make_changes",
                        "active",
                        on_event,
                        detail="Repairing failed validation",
                    )
                    messages.append(
                        {
                            "role": "system",
                            "content": validation_failure_prompt(
                                changed_paths=state.changed_paths or set(),
                                summary=state.last_validation_summary,
                                plan=validation_plan,
                                attempt=validation_repair_attempts,
                                max_attempts=self.MAX_VALIDATION_REPAIR_ROUNDS,
                            ),
                        }
                    )
                    if assistant_text and not assistant_text_streamed:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue
                if (
                    (state.mutated or state.content_changed or state.validated or require_tools)
                    and not final_response_forced
                ):
                    final_response_forced = True
                    self._set_phase(state, AgentPhase.FINALIZING, on_event)
                    self._set_plan_step(state, "final_answer", "active", on_event)
                    messages.append(
                        {
                            "role": "system",
                            "content": self._final_response_prompt(state),
                        }
                    )
                    continue

                final_text = assistant_text
                if not final_text:
                    final_text = "已完成。"
                self._set_phase(state, AgentPhase.FINALIZING, on_event)
                self._set_plan_step(state, "final_answer", "done", on_event)
                if state.content_changed and state.validation_failed and state.last_validation_summary:
                    final_text = (
                        f"{final_text}\n\nValidation is still failing after automatic retries.\n"
                        f"Last validation summary: {state.last_validation_summary}"
                    )
                if assistant_text_streamed:
                    report_parts.append(f"\n\n### 结果\n\n{final_text}\n")
                else:
                    self._emit(emit, report_parts, f"### 结果\n\n{final_text}\n")
                self._finish_run_with_trust_check("completed", state, on_event)
                return "".join(report_parts)

            if assistant_text and not assistant_text_streamed:
                self._emit(emit, report_parts, f"{assistant_text}\n\n")

            self._emit(emit, report_parts, f"### 宸ュ叿璋冪敤 {round_idx + 1}\n")
            for tool_call in tool_calls:
                if should_stop and should_stop():
                    self._set_phase(state, AgentPhase.STOPPED, on_event)
                    self._emit(emit, report_parts, "\n> 宸蹭腑姝n")
                    self._finish_run_with_trust_check("stopped", state, on_event)
                    return "".join(report_parts)

                name = tool_call.function.name
                if name in self.VALIDATION_TOOLS:
                    self._set_phase(state, AgentPhase.VALIDATING, on_event)
                elif name in self.MUTATION_TOOLS:
                    self._set_phase(state, AgentPhase.EDITING, on_event)
                elif name in self.INSPECTION_TOOLS:
                    self._set_phase(state, AgentPhase.INSPECTING, on_event)
                else:
                    self._set_phase(state, AgentPhase.PLANNING, on_event)
                self._set_plan_for_tool(
                    state,
                    name,
                    "active",
                    on_event,
                    detail=f"Running tool `{name}`",
                )
                raw_args = tool_call.function.arguments or "{}"
                args: dict[str, Any] = {}
                display_args: dict[str, Any]
                preview_text: str | None = None
                tool_action_emitted = False
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError as exc:
                    display_args = {"raw_arguments": raw_args}
                    self._emit_event(
                        on_event,
                        {
                            "type": "tool_start",
                            "call_id": tool_call.id,
                            "name": name,
                            "args": display_args,
                            "round": round_idx + 1,
                        },
                    )
                    result = {"ok": False, "error": f"Invalid JSON arguments: {exc}", "raw_arguments": raw_args}
                    result_ok = self._tool_result_ok(name, result)
                else:
                    result, result_ok, display_args, preview_text = self._execute_tool_action(
                        call_id=tool_call.id,
                        name=name,
                        args=args,
                        round_idx=round_idx + 1,
                        messages=messages,
                        report_parts=report_parts,
                        emit=emit,
                        on_event=on_event,
                    )
                    tool_action_emitted = True
                self._record_tool_loop_guard(
                    state,
                    name=name,
                    args=args if args else {"raw_arguments": raw_args},
                    result=result,
                    ok=result_ok,
                    messages=messages,
                    on_event=on_event,
                    round_idx=round_idx + 1,
                )
                if name in self.INSPECTION_TOOLS and result_ok:
                    state.inspected = True
                    self._set_plan_step(
                        state,
                        "inspect_context",
                        "done",
                        on_event,
                        detail=f"Completed `{name}`",
                    )
                if name in self.MUTATION_TOOLS and result_ok:
                    state.mutated = True
                    self._set_plan_step(
                        state,
                        "make_changes",
                        "done",
                        on_event,
                        detail=f"Completed `{name}`",
                    )
                    if state.changed_paths is not None:
                        state.changed_paths.update(self._paths_touched_by_tool(name, result))
                    if name in self.CONTENT_EDIT_TOOLS:
                        state.content_changed = True
                        state.validated = False
                        validation_retry_forced = False
                        final_response_forced = False
                        validation_repair_attempts = 0
                        state.validation_failed = False
                        state.last_validation_summary = None
                        validation_plan = None
                        validation_plan_announced = False
                if name in self.VALIDATION_TOOLS:
                    state.validated = True
                    state.validation_failed = not result_ok
                    if state.validation_failed:
                        state.last_validation_summary = str(
                            result.get("summary")
                            or result.get("error")
                            or result.get("stderr")
                            or result.get("stdout")
                            or ""
                        ).strip() or None
                    else:
                        state.last_validation_summary = str(result.get("summary") or "").strip() or None
                    self._set_plan_step(
                        state,
                        "validate_changes",
                        "failed" if state.validation_failed else "done",
                        on_event,
                        detail=state.last_validation_summary,
                    )
                if not result_ok:
                    state.failed_tool_count += 1
                    self._set_plan_for_tool(
                        state,
                        name,
                        "failed",
                        on_event,
                        detail=str(
                            result.get("summary")
                            or result.get("error")
                            or result.get("stderr")
                            or result.get("stdout")
                            or f"`{name}` failed"
                        ).strip()[:500],
                    )

                if not tool_action_emitted:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result_json_for_model(name, result),
                        }
                    )

                    self._emit_event(
                        on_event,
                        {
                            "type": "tool_result",
                            "call_id": tool_call.id,
                            "name": name,
                            "args": display_args,
                            "result": result,
                            "round": round_idx + 1,
                            "ok": result_ok,
                        },
                    )

                    self._emit(
                        emit,
                        report_parts,
                        tool_report_section(name, display_args, result, preview=preview_text),
                    )

        self._emit(
            emit,
            report_parts,
            "### 结果\n\n"
            "已达到最大轮次限制，未能自动收敛到最终答案。"
            "请查看工具输出，或者再发一条更明确的指令继续。",
        )
        self._finish_run_with_trust_check("max_rounds", state, on_event)
        return "".join(report_parts)
