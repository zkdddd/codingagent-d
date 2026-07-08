from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
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
    MAX_VALIDATION_REPAIR_ROUNDS = 3
    MAX_VALIDATION_PLAN_COMMANDS = 2

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
    def _shell_command(parts: list[str]) -> str:
        return subprocess.list2cmdline(parts)

    def _workspace_path_exists(self, relative_path: str, base: Path | None = None) -> bool:
        root = base or self.workspace.root
        return (root / relative_path).exists()

    def _read_workspace_text(
        self,
        relative_path: str,
        limit: int = 20000,
        base: Path | None = None,
    ) -> str:
        root = base or self.workspace.root
        path = root / relative_path
        if not path.exists() or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")[:limit]
        except Exception:
            return ""

    def _normalize_changed_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (self.workspace.root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        return candidate

    def _candidate_project_roots(self, changed_paths: set[str]) -> list[Path]:
        candidates: list[Path] = []
        for raw_path in sorted(path for path in changed_paths if path):
            current = self._normalize_changed_path(raw_path)
            if current.suffix:
                current = current.parent
            while True:
                if current == self.workspace.root or self.workspace.root in current.parents:
                    if current not in candidates:
                        candidates.append(current)
                if current == self.workspace.root:
                    break
                current = current.parent
        if self.workspace.root not in candidates:
            candidates.append(self.workspace.root)
        candidates.sort(key=lambda path: len(path.parts), reverse=True)
        return candidates

    def _find_project_root(self, changed_paths: set[str], markers: tuple[str, ...]) -> Path | None:
        for candidate in self._candidate_project_roots(changed_paths):
            if any((candidate / marker).exists() for marker in markers):
                return candidate
        return None

    def _package_json_scripts(self, project_root: Path) -> dict[str, Any]:
        package_json = project_root / "package.json"
        if not package_json.exists():
            return {}
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except Exception:
            return {}
        scripts = data.get("scripts")
        return scripts if isinstance(scripts, dict) else {}

    def _detect_validation_project(self, changed_paths: set[str]) -> tuple[str, Path | None]:
        suffixes = {Path(path).suffix.lower() for path in changed_paths if path}
        node_root = self._find_project_root(changed_paths, ("package.json",))
        if node_root is not None:
            return "node", node_root
        python_root = self._find_project_root(
            changed_paths,
            ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"),
        )
        if (
            python_root is not None
            or ".py" in suffixes
        ):
            return "python", python_root
        rust_root = self._find_project_root(changed_paths, ("Cargo.toml",))
        if rust_root is not None:
            return "rust", rust_root
        go_root = self._find_project_root(changed_paths, ("go.mod",))
        if go_root is not None:
            return "go", go_root
        java_root = self._find_project_root(changed_paths, ("pom.xml", "build.gradle", "build.gradle.kts"))
        if (
            java_root is not None
        ):
            return "java", java_root
        cpp_root = self._find_project_root(changed_paths, ("CMakeLists.txt", "Makefile"))
        if (
            cpp_root is not None
            or suffixes.intersection({".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"})
        ):
            return "cpp", cpp_root
        if suffixes and suffixes.issubset({".md", ".txt", ".rst", ".json", ".yml", ".yaml", ".toml"}):
            return "docs", None
        return "generic", None

    def _python_validation_commands(
        self,
        changed_paths: set[str],
        project_root: Path | None,
    ) -> list[dict[str, Any]]:
        commands: list[dict[str, Any]] = []
        command_cwd = self.workspace._rel(project_root) if project_root is not None else "."
        changed_py_files = sorted(
            str(self._normalize_changed_path(path))
            for path in changed_paths
            if Path(path).suffix.lower() == ".py"
        )[:20]
        if changed_py_files:
            commands.append(
                {
                    "label": "Python syntax check",
                    "reason": "Compile the changed Python files to catch syntax errors quickly.",
                    "command": self._shell_command(
                        [sys.executable, "-m", "py_compile", *changed_py_files]
                    ),
                    "cwd": command_cwd,
                    "timeout_ms": 120000,
                }
            )
        else:
            compile_targets: list[str] = []
            search_root = project_root or self.workspace.root
            if self._workspace_path_exists("main.py", base=search_root):
                compile_targets.append(str((search_root / "main.py").resolve()))
            for candidate in ("kagent", "src", "app", "tests"):
                if self._workspace_path_exists(candidate, base=search_root):
                    compile_targets.append(str((search_root / candidate).resolve()))
            if not compile_targets:
                compile_targets.append(str(search_root.resolve()))
            commands.append(
                {
                    "label": "Python compileall",
                    "reason": "Compile the Python entrypoints and packages when no direct .py file list is available.",
                    "command": self._shell_command(
                        [sys.executable, "-m", "compileall", *compile_targets[:6]]
                    ),
                    "cwd": command_cwd,
                    "timeout_ms": 120000,
                }
            )

        search_root = project_root or self.workspace.root
        has_pytest = (
            self._workspace_path_exists("tests", base=search_root)
            or self._workspace_path_exists("pytest.ini", base=search_root)
            or self._workspace_path_exists("tox.ini", base=search_root)
            or "[tool.pytest" in self._read_workspace_text("pyproject.toml", base=search_root).lower()
        )
        if has_pytest:
            commands.append(
                {
                    "label": "Pytest suite",
                    "reason": "Run the test suite after the lightweight syntax validation.",
                    "command": self._shell_command([sys.executable, "-m", "pytest", "-q"]),
                    "cwd": command_cwd,
                    "timeout_ms": 240000,
                }
            )
        return commands[: self.MAX_VALIDATION_PLAN_COMMANDS]

    def _node_validation_commands(self, project_root: Path) -> list[dict[str, Any]]:
        scripts = self._package_json_scripts(project_root)
        if not scripts:
            return []
        command_cwd = self.workspace._rel(project_root)
        package_manager = "npm"
        if self._workspace_path_exists("pnpm-lock.yaml", base=project_root):
            package_manager = "pnpm"
        elif self._workspace_path_exists("yarn.lock", base=project_root):
            package_manager = "yarn"

        script_priority = [
            ("typecheck", "Type check", 180000),
            ("lint", "Lint", 180000),
            ("test", "Test suite", 240000),
            ("build", "Build", 240000),
        ]
        commands: list[dict[str, Any]] = []
        for script_name, label, timeout_ms in script_priority:
            if script_name not in scripts:
                continue
            commands.append(
                {
                    "label": label,
                    "reason": f"Run the `{script_name}` script declared in package.json.",
                    "command": f"{package_manager} run {script_name}",
                    "cwd": command_cwd,
                    "timeout_ms": timeout_ms,
                }
            )
        return commands[: self.MAX_VALIDATION_PLAN_COMMANDS]

    def _build_validation_plan(self, changed_paths: set[str]) -> dict[str, Any]:
        project_type, project_root = self._detect_validation_project(changed_paths)
        changed_list = sorted(str(path) for path in changed_paths if path)
        commands: list[dict[str, Any]]

        if project_type == "python":
            commands = self._python_validation_commands(changed_paths, project_root)
        elif project_type == "node":
            commands = self._node_validation_commands(project_root or self.workspace.root)
        elif project_type == "rust":
            commands = [
                {
                    "label": "Cargo check",
                    "reason": "Run a fast Rust compile check.",
                    "command": "cargo check",
                    "cwd": self.workspace._rel(project_root) if project_root is not None else ".",
                    "timeout_ms": 240000,
                }
            ]
        elif project_type == "go":
            commands = [
                {
                    "label": "Go test",
                    "reason": "Run the Go package tests for the workspace.",
                    "command": "go test ./...",
                    "cwd": self.workspace._rel(project_root) if project_root is not None else ".",
                    "timeout_ms": 240000,
                }
            ]
        else:
            commands = []

        if commands:
            summary = (
                f"Detected a {project_type} project and prepared {len(commands)} validation command"
                f"{'s' if len(commands) != 1 else ''}. First step: {commands[0]['label']}."
            )
        elif project_type == "docs":
            summary = (
                "No meaningful automatic validation command was selected because the changes look like "
                "documentation or config-only edits."
            )
        else:
            summary = (
                "No safe automatic validation command was detected for this project layout. "
                "The final answer should explain that validation was not available."
            )

        return {
            "project_type": project_type,
            "summary": summary,
            "changed_paths": changed_list[:12],
            "project_root": self.workspace._rel(project_root) if project_root is not None else ".",
            "commands": commands,
            "command_count": len(commands),
        }

    def _validation_prompt(
        self,
        changed_paths: set[str],
        plan: dict[str, Any] | None = None,
    ) -> str:
        files = ", ".join(sorted(changed_paths)[:8]) if changed_paths else "the changed files"
        if not isinstance(plan, dict):
            return (
                "You changed workspace files and are about to finish. "
                f"Before the final answer, run at least one validation command for {files}. "
                "Choose the most relevant lightweight check for the project and the edited files. "
                "If no meaningful validation exists, explicitly explain why."
            )

        commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
        if not commands:
            return (
                f"No safe automatic validation command was found for {files}. "
                "Explain that limitation explicitly in the final answer."
            )
        command_lines = []
        for idx, command_info in enumerate(commands, start=1):
            if not isinstance(command_info, dict):
                continue
            command_lines.append(
                f"{idx}. {command_info.get('label')}: `{command_info.get('command')}`"
            )
        commands_text = "\n".join(command_lines)
        return (
            "You changed workspace files and are about to finish. "
            f"Before the final answer, validate {files}.\n"
            f"Detected project type: {plan.get('project_type', 'generic')}.\n"
            "Prefer these commands in order:\n"
            f"{commands_text}\n"
            "If every command is unsuitable, explicitly explain why."
        )

    def _validation_failure_prompt(
        self,
        changed_paths: set[str],
        summary: str | None,
        plan: dict[str, Any] | None = None,
        attempt: int = 1,
    ) -> str:
        files = ", ".join(sorted(changed_paths)[:8]) if changed_paths else "the changed files"
        detail = f" Last validation summary: {summary}." if summary else ""
        plan_text = ""
        if isinstance(plan, dict):
            commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
            command_lines = []
            for idx, command_info in enumerate(commands, start=1):
                if not isinstance(command_info, dict):
                    continue
                command_lines.append(
                    f"{idx}. {command_info.get('label')}: `{command_info.get('command')}`"
                )
            if command_lines:
                plan_text = (
                    "\nUse the validation plan again after fixing the issue:\n"
                    + "\n".join(command_lines)
                )
        return (
            f"The last validation failed after you changed workspace files.{detail} "
            f"This is repair attempt {attempt} of {self.MAX_VALIDATION_REPAIR_ROUNDS}. "
            "Inspect the failure, fix the real issue, and validate again before finishing. "
            f"Focus on {files}.{plan_text}"
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

        display_args = self._tool_display_args(name, args)
        preview_text = self._tool_preview_text(name, args)
        self._emit_event(
            on_event,
            {
                "type": "tool_start",
                "call_id": call_id,
                "name": name,
                "args": display_args,
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
                    "round": round_idx,
                },
            )

        approved = True
        if self._tool_requires_approval(name) and self.confirm_tool is not None:
            approved = bool(
                self.confirm_tool(
                    call_id,
                    name,
                    display_args,
                    preview_text,
                    round_idx,
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
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(result, ensure_ascii=False),
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
                "round": round_idx,
                "ok": result_ok,
            },
        )
        self._emit(
            emit,
            report_parts,
            self._tool_report_section(name, display_args, result, preview=preview_text),
        )
        return result, result_ok, display_args, preview_text

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
            self._tool_report_section("validation_plan", args, result),
        )

    def _run_auto_validation(
        self,
        *,
        plan: dict[str, Any],
        validation_run_seq: int,
        round_idx: int,
        messages: list[dict[str, Any]],
        report_parts: list[str],
        emit: EmitFn | None,
        on_event: EventFn | None,
    ) -> tuple[bool, str | None, int]:
        commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
        if not commands:
            return True, str(plan.get("summary") or "").strip() or None, 0

        self._emit_event(
            on_event,
            {
                "type": "agent_status",
                "status": "Validating",
                "kind": "active",
            },
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
            last_summary = str(
                result.get("summary")
                or result.get("error")
                or result.get("stderr")
                or result.get("stdout")
                or command_info.get("label")
                or ""
            ).strip() or None
            if not result_ok:
                self._emit_event(
                    on_event,
                    {
                        "type": "agent_status",
                        "status": "Repairing",
                        "kind": "active",
                    },
                )
                return False, last_summary, executed

        self._emit_event(
            on_event,
            {
                "type": "agent_status",
                "status": "Validated",
                "kind": "active",
            },
        )
        return True, last_summary, executed

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
        validation_repair_attempts = 0
        validation_plan_run_seq = 0
        inspected = False
        mutated = False
        content_changed = False
        validated = False
        validation_failed = False
        changed_paths: set[str] = set()
        last_validation_summary: str | None = None
        validation_plan: dict[str, Any] | None = None
        validation_plan_announced = False
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

            if content_changed and not validated:
                if validation_plan is None:
                    validation_plan = self._build_validation_plan(changed_paths)
                if not validation_plan_announced:
                    validation_plan_run_seq += 1
                    self._emit_validation_plan(
                        call_id=f"validation-plan-{validation_plan_run_seq}",
                        plan=validation_plan,
                        changed_paths=changed_paths,
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
                if plan_commands:
                    validation_plan_run_seq += 1
                    ok, summary, executed = self._run_auto_validation(
                        plan=validation_plan,
                        validation_run_seq=validation_plan_run_seq,
                        round_idx=round_idx + 1,
                        messages=messages,
                        report_parts=report_parts,
                        emit=emit,
                        on_event=on_event,
                    )
                    validated = True
                    validation_failed = not ok
                    last_validation_summary = summary
                    if executed > 0:
                        validation_retry_forced = True
                    continue

                validated = True
                validation_failed = False
                last_validation_summary = str(validation_plan.get("summary") or "").strip() or None
                messages.append(
                    {
                        "role": "system",
                        "content": self._validation_prompt(changed_paths, validation_plan),
                    }
                )
                continue

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
                            "content": self._validation_prompt(changed_paths, validation_plan),
                        }
                    )
                    if assistant_text:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue
                if (
                    content_changed
                    and validation_failed
                    and validation_repair_attempts < self.MAX_VALIDATION_REPAIR_ROUNDS
                ):
                    validation_repair_attempts += 1
                    self._emit_event(
                        on_event,
                        {
                            "type": "agent_status",
                            "status": "Repairing",
                            "kind": "active",
                        },
                    )
                    messages.append(
                        {
                            "role": "system",
                            "content": self._validation_failure_prompt(
                                changed_paths,
                                last_validation_summary,
                                validation_plan,
                                attempt=validation_repair_attempts,
                            ),
                        }
                    )
                    if assistant_text:
                        self._emit(emit, report_parts, f"{assistant_text}\n\n")
                    continue
                final_text = assistant_text
                if not final_text:
                    final_text = "已完成。"
                if content_changed and validation_failed and last_validation_summary:
                    final_text = (
                        f"{final_text}\n\nValidation is still failing after automatic retries.\n"
                        f"Last validation summary: {last_validation_summary}"
                    )
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
                if name in self.INSPECTION_TOOLS and result_ok:
                    inspected = True
                if name in self.MUTATION_TOOLS and result_ok:
                    mutated = True
                    changed_paths.update(self._paths_touched_by_tool(name, result))
                    if name in self.CONTENT_EDIT_TOOLS:
                        content_changed = True
                        validated = False
                        validation_retry_forced = False
                        validation_repair_attempts = 0
                        validation_failed = False
                        last_validation_summary = None
                        validation_plan = None
                        validation_plan_announced = False
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

                if not tool_action_emitted:
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
