from __future__ import annotations

import json
from typing import Any, Callable

from ..config import AGENT_SYSTEM_PROMPT, MODEL
from ..llm import client
from .workspace import WorkspaceError, WorkspaceTools

EmitFn = Callable[[str], None]
StopFn = Callable[[], bool]


def _tool_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a UTF-8 text file from the workspace. Paths should be relative to the workspace root when possible.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path relative to the workspace root or an absolute path inside the workspace."},
                        "start_line": {"type": "integer", "minimum": 1, "description": "Optional 1-based starting line."},
                        "end_line": {"type": "integer", "minimum": 1, "description": "Optional 1-based ending line."},
                        "max_chars": {"type": "integer", "minimum": 1, "description": "Maximum characters to return from the selected range."},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Overwrite a UTF-8 text file inside the workspace with the provided full content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path relative to the workspace root or an absolute path inside the workspace."},
                        "content": {"type": "string", "description": "Full file content to write."},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Run a shell command inside the workspace root or an allowed workspace subdirectory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to run."},
                        "cwd": {"type": "string", "description": "Optional working directory relative to the workspace root or an absolute path inside the workspace."},
                        "timeout_ms": {"type": "integer", "minimum": 1, "description": "Command timeout in milliseconds."},
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
            },
        },
    ]


class CodeAgent:
    def __init__(self, workspace_root: str | None = None, model: str = MODEL):
        self.workspace = WorkspaceTools(workspace_root) if workspace_root else WorkspaceTools()
        self.model = model

    @staticmethod
    def _json_block(data: Any, limit: int = 3500) -> str:
        text = json.dumps(data, ensure_ascii=False, indent=2)
        truncated = False
        if len(text) > limit:
            text = text[:limit] + "\n... (truncated)"
            truncated = True
        return f"```json\n{text}\n```" + ("\n" if truncated else "")

    @staticmethod
    def _text_block(text: str, limit: int = 4500) -> str:
        truncated = False
        if len(text) > limit:
            text = text[:limit] + "\n... (truncated)"
            truncated = True
        return f"```text\n{text}\n```" + ("\n" if truncated else "")

    def _emit(self, emit: EmitFn | None, parts: list[str], text: str) -> None:
        parts.append(text)
        if emit:
            emit(text)

    def _dispatch_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
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
        if name == "run_command":
            return self.workspace.run_command(
                command=str(args["command"]),
                cwd=args.get("cwd"),
                timeout_ms=int(args.get("timeout_ms", 120000)),
            )
        raise WorkspaceError(f"Unknown tool: {name}")

    def run(
        self,
        history: list[dict[str, Any]],
        emit: EmitFn | None = None,
        should_stop: StopFn | None = None,
        max_rounds: int = 12,
    ) -> str:
        if not history:
            raise WorkspaceError("history is required")

        user_task = ""
        for item in reversed(history):
            if item.get("role") == "user":
                user_task = str(item.get("content", ""))
                break

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": AGENT_SYSTEM_PROMPT.format(workspace_root=str(self.workspace.root)),
            }
        ]
        for item in history:
            if item.get("role") in ("user", "assistant"):
                messages.append(
                    {
                        "role": item["role"],
                        "content": str(item.get("content", "")),
                    }
                )

        report_parts: list[str] = []
        self._emit(
            emit,
            report_parts,
            "### 任务\n\n"
            f"{user_task}\n\n"
            f"### 工作区\n\n`{self.workspace.root}`\n",
        )

        for round_idx in range(max_rounds):
            if should_stop and should_stop():
                self._emit(emit, report_parts, "\n> 已中止\n")
                return "".join(report_parts)

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=_tool_schema(),
                tool_choice="auto",
                temperature=0.2,
            )

            assistant = response.choices[0].message
            assistant_dump = assistant.model_dump(exclude_none=True)
            messages.append(assistant_dump)

            tool_calls = assistant.tool_calls or []
            assistant_text = (assistant.content or "").strip()
            if not tool_calls:
                final_text = assistant_text
                if not final_text:
                    final_text = "已完成。"
                self._emit(emit, report_parts, f"### 结果\n\n{final_text}\n")
                return "".join(report_parts)

            if assistant_text:
                self._emit(emit, report_parts, f"{assistant_text}\n\n")

            self._emit(emit, report_parts, f"### 工具调用 {round_idx + 1}\n")
            for tool_call in tool_calls:
                if should_stop and should_stop():
                    self._emit(emit, report_parts, "\n> 已中止\n")
                    return "".join(report_parts)

                name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                args: dict[str, Any] = {}
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError as exc:
                    result = {"ok": False, "error": f"Invalid JSON arguments: {exc}", "raw_arguments": raw_args}
                else:
                    try:
                        result = self._dispatch_tool(name, args)
                    except Exception as exc:
                        result = {"ok": False, "error": str(exc)}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

                tool_section = (
                    f"#### `{name}`\n\n"
                    f"**输入**\n\n{self._json_block(args)}\n"
                    f"**结果**\n\n{self._json_block(result)}\n"
                )
                self._emit(emit, report_parts, tool_section)

        self._emit(
            emit,
            report_parts,
            "### 结果\n\n"
            "已达到最大轮次限制，未能自动收敛到最终答案。"
            " 请查看工具输出，或者再发一条更明确的指令继续。",
        )
        return "".join(report_parts)
