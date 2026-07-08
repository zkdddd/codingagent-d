from __future__ import annotations

import json
from typing import Any, Callable

from ..config import AGENT_SYSTEM_PROMPT, MODEL
from ..llm import AGENT_REQUEST_TIMEOUT_SECONDS, client
from .workspace import WorkspaceError, WorkspaceTools

EmitFn = Callable[[str], None]
EventFn = Callable[[dict[str, Any]], None]
StopFn = Callable[[], bool]
ConfirmFn = Callable[[str, str, dict[str, Any], str | None, int | None], bool]

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
11. preview_rollback_change when the user wants to inspect the exact diff for a rollback record.
12. rollback_last_change or rollback_change when the user explicitly asks to undo workspace changes in this chat session.

Prefer small, reviewable changes. If a command fails, inspect the output and fix the real cause before continuing.
If the task requires checking files, changing files, renaming paths, or running commands, do not stop after saying what you will do. In the same turn, call the next tool and continue the task.
"""


def _tool_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories in the workspace. Use this to inspect project structure before reading files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path relative to the workspace root or an absolute path inside the workspace."},
                        "max_depth": {"type": "integer", "minimum": 0, "description": "Maximum depth below the start path."},
                        "include_dirs": {"type": "boolean", "description": "Whether to include directories in the listing."},
                        "include_hidden": {"type": "boolean", "description": "Whether to include hidden files and directories."},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 2000, "description": "Maximum number of entries to return."},
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_file",
                "description": "Search text inside workspace files and return matching lines with context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for."},
                        "path": {"type": "string", "description": "Directory or file path relative to the workspace root or an absolute path inside the workspace."},
                        "file_glob": {"type": "string", "description": "Optional filename glob such as *.py or *.md."},
                        "case_sensitive": {"type": "boolean", "description": "Whether the search should be case sensitive."},
                        "include_hidden": {"type": "boolean", "description": "Whether to include hidden files and directories."},
                        "context_lines": {"type": "integer", "minimum": 0, "description": "Number of surrounding lines to include."},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 1000, "description": "Maximum number of matches to return."},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
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
                "name": "rename_path",
                "description": "Rename or move a file or directory inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_path": {"type": "string", "description": "Existing file or directory path inside the workspace."},
                        "target_path": {"type": "string", "description": "New file or directory path inside the workspace."},
                    },
                    "required": ["source_path", "target_path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "copy_path",
                "description": "Copy a file or directory inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_path": {"type": "string", "description": "Existing file or directory path inside the workspace."},
                        "target_path": {"type": "string", "description": "Destination path inside the workspace."},
                    },
                    "required": ["source_path", "target_path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_path",
                "description": "Delete a file or directory inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Existing file or directory path inside the workspace."},
                        "recursive": {"type": "boolean", "description": "Whether to delete directories recursively. Defaults to true."},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "make_directory",
                "description": "Create a directory inside the workspace when its parent already exists.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to create inside the workspace."},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "apply_patch",
                "description": "Apply a unified diff patch to files inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patch": {"type": "string", "description": "A unified diff patch beginning with diff --git lines."},
                    },
                    "required": ["patch"],
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
        {
            "type": "function",
            "function": {
                "name": "list_rollback_history",
                "description": "List recent rollback records for this chat session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Maximum number of rollback entries to return."},
                        "include_inactive": {"type": "boolean", "description": "Whether to include already applied or superseded rollback entries."},
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "preview_rollback_change",
                "description": "Preview the exact file diff for a specific rollback history id without applying it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rollback_id": {"type": "integer", "minimum": 1, "description": "The rollback history id to inspect."},
                    },
                    "required": ["rollback_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "rollback_last_change",
                "description": "Undo the most recent workspace mutation recorded for this chat session.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "rollback_change",
                "description": "Undo a specific rollback record by its rollback_id in this chat session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rollback_id": {"type": "integer", "minimum": 1, "description": "The rollback history id to restore."},
                    },
                    "required": ["rollback_id"],
                    "additionalProperties": False,
                },
            },
        },
    ]


class CodeAgent:
    INSPECTION_TOOLS = {
        "list_files",
        "search_file",
        "read_file",
        "list_rollback_history",
        "preview_rollback_change",
    }
    CONTENT_EDIT_TOOLS = {
        "write_file",
        "apply_patch",
        "rollback_last_change",
        "rollback_change",
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
    }
    VALIDATION_TOOLS = {"run_command"}

    def __init__(
        self,
        workspace_root: str | None = None,
        model: str = MODEL,
        confirm_tool: ConfirmFn | None = None,
        session_id: str | None = None,
    ):
        self.workspace = (
            WorkspaceTools(workspace_root, session_id=session_id)
            if workspace_root
            else WorkspaceTools(session_id=session_id)
        )
        self.model = model
        self.confirm_tool = confirm_tool

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
        if name in {"rollback_last_change", "rollback_change"}:
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

    @staticmethod
    def _validation_prompt(changed_paths: set[str]) -> str:
        files = ", ".join(sorted(changed_paths)[:8]) if changed_paths else "the changed files"
        return (
            "You changed workspace files and are about to finish. "
            f"Before the final answer, run at least one validation command for {files}. "
            "Choose the most relevant lightweight check for the project and the edited files. "
            "If no meaningful validation exists, explicitly explain why."
        )

    @staticmethod
    def _validation_failure_prompt(changed_paths: set[str], summary: str | None) -> str:
        files = ", ".join(sorted(changed_paths)[:8]) if changed_paths else "the changed files"
        detail = f" Last validation summary: {summary}." if summary else ""
        return (
            "The last validation failed after you changed workspace files."
            f"{detail} Inspect the failure, fix the real issue, and validate again before finishing. "
            f"Focus on {files}."
        )

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

    def _tool_display_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "write_file":
            preview = self.workspace.preview_write_file(
                path=str(args["path"]),
                content=str(args["content"]),
            )
            return {
                "path": preview["path"],
                "exists": preview["exists"],
                "bytes_written": preview["bytes_written"],
                "line_count": preview["line_count"],
                "preview_truncated": preview["preview_truncated"],
            }

        if name == "run_command":
            preview = self.workspace.preview_command(
                command=str(args["command"]),
                cwd=args.get("cwd"),
                timeout_ms=int(args.get("timeout_ms", 120000)),
            )
            return {
                "command": preview["command"],
                "cwd": preview["cwd"],
                "timeout_ms": preview["timeout_ms"],
            }

        if name == "rename_path":
            preview = self.workspace.preview_rename_path(
                source_path=str(args["source_path"]),
                target_path=str(args["target_path"]),
            )
            return {
                "source_path": preview["source_path"],
                "target_path": preview["target_path"],
                "item_type": preview["item_type"],
            }

        if name == "copy_path":
            preview = self.workspace.preview_copy_path(
                source_path=str(args["source_path"]),
                target_path=str(args["target_path"]),
            )
            return {
                "source_path": preview["source_path"],
                "target_path": preview["target_path"],
                "item_type": preview["item_type"],
                "item_count": preview["item_count"],
                "item_count_truncated": preview["item_count_truncated"],
            }

        if name == "delete_path":
            preview = self.workspace.preview_delete_path(
                path=str(args["path"]),
                recursive=bool(args.get("recursive", True)),
            )
            return {
                "path": preview["path"],
                "item_type": preview["item_type"],
                "recursive": preview["recursive"],
                "item_count": preview["item_count"],
                "item_count_truncated": preview["item_count_truncated"],
            }

        if name == "make_directory":
            preview = self.workspace.preview_make_directory(
                path=str(args["path"]),
            )
            return {
                "path": preview["path"],
                "exists": preview["exists"],
            }

        if name == "list_rollback_history":
            limit = int(args.get("limit", 12))
            include_inactive = bool(args.get("include_inactive", True))
            return {
                "limit": limit,
                "include_inactive": include_inactive,
            }

        if name == "preview_rollback_change":
            preview = self.workspace.preview_rollback_change(
                rollback_id=int(args["rollback_id"]),
            )
            return {
                "rollback_id": preview["rollback_id"],
                "source_tool": preview["source_tool"],
                "created_at": preview["created_at"],
                "status": preview["status"],
                "available": preview["available"],
                "path_count": preview["path_count"],
                "paths": preview["paths"][:12],
                "paths_truncated": len(preview["paths"]) > 12,
                "preview_truncated": preview["preview_truncated"],
                "superseded_active_count": preview["superseded_active_count"],
            }

        if name == "rollback_last_change":
            preview = self.workspace.preview_rollback_last_change()
            return {
                "rollback_id": preview["rollback_id"],
                "source_tool": preview["source_tool"],
                "created_at": preview["created_at"],
                "status": preview["status"],
                "available": preview["available"],
                "path_count": preview["path_count"],
                "paths": preview["paths"][:12],
                "paths_truncated": len(preview["paths"]) > 12,
            }

        if name == "rollback_change":
            preview = self.workspace.preview_rollback_change(
                rollback_id=int(args["rollback_id"]),
            )
            return {
                "rollback_id": preview["rollback_id"],
                "source_tool": preview["source_tool"],
                "created_at": preview["created_at"],
                "status": preview["status"],
                "available": preview["available"],
                "path_count": preview["path_count"],
                "paths": preview["paths"][:12],
                "paths_truncated": len(preview["paths"]) > 12,
                "superseded_active_count": preview["superseded_active_count"],
            }

        if name != "apply_patch":
            return args

        patch = str(args.get("patch") or "")
        if not patch.strip():
            return {
                "patch_bytes": 0,
                "patch_lines": 0,
                "file_count": 0,
                "files_touched": [],
            }
        return self.workspace.preview_patch(patch)

    def _tool_preview_text(self, name: str, args: dict[str, Any]) -> str | None:
        if name == "apply_patch":
            patch = str(args.get("patch") or "")
            return patch or None
        if name == "write_file":
            preview = self.workspace.preview_write_file(
                path=str(args["path"]),
                content=str(args["content"]),
            )
            return str(preview["preview"])
        if name == "run_command":
            preview = self.workspace.preview_command(
                command=str(args["command"]),
                cwd=args.get("cwd"),
                timeout_ms=int(args.get("timeout_ms", 120000)),
            )
            return str(preview["preview"])
        if name == "rename_path":
            preview = self.workspace.preview_rename_path(
                source_path=str(args["source_path"]),
                target_path=str(args["target_path"]),
            )
            return str(preview["preview"])
        if name == "copy_path":
            preview = self.workspace.preview_copy_path(
                source_path=str(args["source_path"]),
                target_path=str(args["target_path"]),
            )
            return str(preview["preview"])
        if name == "delete_path":
            preview = self.workspace.preview_delete_path(
                path=str(args["path"]),
                recursive=bool(args.get("recursive", True)),
            )
            return str(preview["preview"])
        if name == "make_directory":
            preview = self.workspace.preview_make_directory(
                path=str(args["path"]),
            )
            return str(preview["preview"])
        if name == "list_rollback_history":
            history = self.workspace.list_rollback_history(
                limit=int(args.get("limit", 12)),
                include_inactive=bool(args.get("include_inactive", True)),
            )
            return str(history["preview"])
        if name == "preview_rollback_change":
            preview = self.workspace.preview_rollback_change(
                rollback_id=int(args["rollback_id"]),
            )
            return str(preview["preview"])
        if name == "rollback_last_change":
            preview = self.workspace.preview_rollback_last_change()
            return str(preview["preview"])
        if name == "rollback_change":
            preview = self.workspace.preview_rollback_change(
                rollback_id=int(args["rollback_id"]),
            )
            return str(preview["preview"])
        return None

    @staticmethod
    def _tool_requires_approval(name: str) -> bool:
        return name in {
            "apply_patch",
            "write_file",
            "rename_path",
            "copy_path",
            "delete_path",
            "make_directory",
            "run_command",
            "rollback_last_change",
            "rollback_change",
        }

    def _tool_report_section(
        self,
        name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        preview: str | None = None,
    ) -> str:
        parts = [
            f"#### `{name}`",
            "",
            "**输入**",
            "",
            self._json_block(args),
        ]
        if preview:
            parts.extend(["**预览**", "", f"```diff\n{preview}\n```", ""])
        parts.extend(
            [
                "**结果**",
                "",
                self._json_block(result),
            ]
        )
        return "\n".join(parts)

    def _emit(self, emit: EmitFn | None, parts: list[str], text: str) -> None:
        parts.append(text)
        if emit:
            emit(text)

    def _emit_event(self, on_event: EventFn | None, event: dict[str, Any]) -> None:
        if on_event:
            on_event(event)

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
        if name == "rollback_last_change":
            return self.workspace.rollback_last_change()
        if name == "rollback_change":
            return self.workspace.rollback_change(
                rollback_id=int(args["rollback_id"]),
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
                    + AGENT_WORKFLOW_HINT
                ),
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
        tool_retry_forced = False
        require_tools = self._task_requires_tools(user_task)
        require_code_inspection = self._task_requires_code_edit(user_task)
        inspection_retry_forced = False
        validation_retry_forced = False
        validation_failure_retry_forced = False
        inspected = False
        mutated = False
        content_changed = False
        validated = False
        validation_failed = False
        changed_paths: set[str] = set()
        last_validation_summary: str | None = None
        self._emit_event(
            on_event,
            {
                "type": "agent_start",
                "task": user_task,
                "workspace_root": str(self.workspace.root),
            },
        )
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
                timeout=AGENT_REQUEST_TIMEOUT_SECONDS,
            )

            assistant = response.choices[0].message
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
                    and not inspected
                    and current_has_content_edit
                    and not current_has_inspection
                    and not inspection_retry_forced
                ):
                    inspection_retry_forced = True
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Before editing code, inspect the relevant project structure and file contents first. "
                                "Use list_files, search_file, or read_file to gather context, then edit."
                            ),
                        }
                    )
                    if assistant_text:
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
                    if assistant_text:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue
                if content_changed and not validated and not validation_retry_forced:
                    validation_retry_forced = True
                    messages.append(
                        {
                            "role": "system",
                            "content": self._validation_prompt(changed_paths),
                        }
                    )
                    if assistant_text:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue
                if (
                    content_changed
                    and validation_failed
                    and not validation_failure_retry_forced
                ):
                    validation_failure_retry_forced = True
                    messages.append(
                        {
                            "role": "system",
                            "content": self._validation_failure_prompt(
                                changed_paths,
                                last_validation_summary,
                            ),
                        }
                    )
                    if assistant_text:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue
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
                display_args: dict[str, Any]
                preview_text: str | None = None
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
                else:
                    display_args = self._tool_display_args(name, args)
                    preview_text = self._tool_preview_text(name, args)
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
                    if preview_text:
                        self._emit_event(
                            on_event,
                            {
                                "type": "tool_preview",
                                "call_id": tool_call.id,
                                "name": name,
                                "args": display_args,
                                "preview": preview_text,
                                "round": round_idx + 1,
                            },
                        )
                    approved = True
                    if self._tool_requires_approval(name) and self.confirm_tool is not None:
                        approved = bool(
                            self.confirm_tool(
                                tool_call.id,
                                name,
                                display_args,
                                preview_text,
                                round_idx + 1,
                            )
                        )

                    if not approved:
                        result = {
                            "ok": False,
                            "error": "Action rejected by user approval gate.",
                            "rejected": True,
                        }
                    else:
                        try:
                            result = self._dispatch_tool(name, args)
                        except Exception as exc:
                            result = {"ok": False, "error": str(exc)}

                result_ok = self._tool_result_ok(name, result)
                if name in self.INSPECTION_TOOLS and result_ok:
                    inspected = True
                if name in self.MUTATION_TOOLS and result_ok:
                    mutated = True
                    changed_paths.update(self._paths_touched_by_tool(name, result))
                    if name in self.CONTENT_EDIT_TOOLS:
                        content_changed = True
                        validated = False
                        validation_retry_forced = False
                        validation_failure_retry_forced = False
                        validation_failed = False
                        last_validation_summary = None
                if name in self.VALIDATION_TOOLS:
                    validated = True
                    validation_failed = not result_ok
                    if validation_failed:
                        last_validation_summary = str(
                            result.get("summary")
                            or result.get("error")
                            or result.get("stderr")
                            or result.get("stdout")
                            or ""
                        ).strip() or None
                    else:
                        last_validation_summary = str(result.get("summary") or "").strip() or None

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
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
                    self._tool_report_section(name, display_args, result, preview=preview_text),
                )

        self._emit(
            emit,
            report_parts,
            "### 结果\n\n"
            "已达到最大轮次限制，未能自动收敛到最终答案。"
            " 请查看工具输出，或者再发一条更明确的指令继续。",
        )
        return "".join(report_parts)
