from __future__ import annotations

from functools import lru_cache
from typing import Any

import jsonschema


@lru_cache(maxsize=1)
def _schema_by_name() -> dict[str, dict[str, Any]]:
    return {
        str(item["function"]["name"]): item["function"].get("parameters") or {}
        for item in tool_schema()
    }


def validate_tool_args(name: str, args: Any) -> list[str]:
    """Validate tool arguments against the declared JSON-Schema.

    Returns a list of human-readable error strings (empty if valid). Unknown
    tools are not validated (returns []), so adding a tool before its schema is
    wired does not block dispatch. Uses jsonschema Draft202012Validator for
    type/required/additionalProperties/minimum/maximum/enum enforcement.
    """
    if not isinstance(args, dict):
        return [f"arguments must be a JSON object, got {type(args).__name__}"]
    schema = _schema_by_name().get(name)
    if not schema:
        return []
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(args), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in error.path) or "(root)"
        errors.append(f"{location}: {error.message}")
    return errors


def tool_schema() -> list[dict[str, Any]]:
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
                "name": "find_symbol",
                "description": "Find class, function, method, import, or language-specific symbol definitions by symbol name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Symbol name to find."},
                        "kind": {"type": "string", "enum": ["class", "function", "method", "import", "interface", "struct", "enum", "type", "trait", "const"], "description": "Optional symbol kind filter."},
                        "exact": {"type": "boolean", "description": "Whether to require an exact symbol name match. Defaults to true."},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200, "description": "Maximum number of matches."},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_symbol_context",
                "description": "Find symbol definitions and return focused source excerpts around each match. Use before editing a known class/function/method.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Symbol name to find."},
                        "kind": {"type": "string", "enum": ["class", "function", "method", "import", "interface", "struct", "enum", "type", "trait", "const"], "description": "Optional symbol kind filter."},
                        "exact": {"type": "boolean", "description": "Whether to require an exact symbol name match. Defaults to true."},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "Maximum number of symbol contexts."},
                        "context_lines": {"type": "integer", "minimum": 0, "maximum": 50, "description": "Surrounding lines before and after the symbol."},
                        "max_chars": {"type": "integer", "minimum": 200, "maximum": 50000, "description": "Maximum characters per returned context."},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_symbol_references",
                "description": "Find files and lines that import, call, or reference a known symbol. Use before changing a function/class to assess impact and related tests.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Symbol name to find references for."},
                        "include_tests": {"type": "boolean", "description": "Whether to include test files. Defaults to true."},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum number of references."},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "symbol_change_plan",
                "description": "Build a symbol-level change plan with definition context, references, related tests, validation commands, and risk summary before editing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol_name": {"type": "string", "description": "Function, class, method, import, or other symbol to change."},
                        "kind": {"type": "string", "enum": ["class", "function", "method", "import", "interface", "struct", "enum", "type", "trait", "const"], "description": "Optional symbol kind filter."},
                        "exact": {"type": "boolean", "description": "Whether to require an exact symbol name match. Defaults to true."},
                        "context_lines": {"type": "integer", "minimum": 0, "maximum": 50, "description": "Source context lines around the symbol definition."},
                        "max_references": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum references to include."},
                    },
                    "required": ["symbol_name"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_untested_symbols",
                "description": (
                    "List production symbols (functions, classes, methods) whose defining source file has no mapped test file — the untested-symbol coverage gap. "
                    "Read-only: it does not edit files or write tests; use scaffold_test_for_symbol to draft a test, then write_file to save it."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 200,
                            "description": "Maximum number of untested symbols to return.",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "measure_coverage",
                "description": (
                    "Run pytest under coverage and return the real line/branch coverage rate plus a trend and a regression gate. "
                    "Persists the snapshot to coverage history so subsequent validation plans rank full-suite commands by real coverage. "
                    "Read-only with respect to project source: it only runs the test suite under coverage and stores a coverage report."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pytest_args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Extra pytest arguments (defaults to -q).",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recall_similar_failures",
                "description": (
                    "Recall past similar test failures from run-log history (a test-failure knowledge base). "
                    "Indexes per-test failures joined with the symbol impacts and change plans of the same run, and returns the closest historical failures by text similarity, including how the change was framed. "
                    "Read-only. Returns insufficient_corpus when the run history is too thin to recall reliably."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Failure description, nodeid, or error message to match."},
                        "k": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Maximum matches to return."},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "scaffold_test_for_symbol",
                "description": (
                    "Generate a pytest scaffold (import + placeholder test functions) for an untested symbol, returning the suggested test file path and its content. "
                    "It does not write the file: review the content, then use write_file to save it and run_command to verify it collects."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Source path of the untested symbol, as returned by list_untested_symbols."},
                        "symbol": {"type": "string", "description": "Symbol name to prioritize in the scaffold."},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "suggest_self_improvements",
                "description": (
                    "Analyze this workspace and suggest small, low-risk coding-agent improvements. "
                    "This is read-only: it does not edit files or run commands."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Maximum number of suggestions to return.",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_project_rules",
                "description": (
                    "Read the workspace KAGENT.md project rules file. "
                    "Use this when a task may depend on local coding style, validation, safety, or workflow rules."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_chars": {
                            "type": "integer",
                            "minimum": 500,
                            "maximum": 50000,
                            "description": "Maximum characters of KAGENT.md content to return.",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_project_rules",
                "description": (
                    "Generate a draft KAGENT.md from current project structure, validation commands, and stable preferences. "
                    "This is read-only and returns draft content; use write_file only after deciding to create or update the file."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_chars": {
                            "type": "integer",
                            "minimum": 500,
                            "maximum": 50000,
                            "description": "Maximum characters of draft KAGENT.md content to return.",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_project_rules",
                "description": (
                    "Check whether KAGENT.md is present and complete enough for coding-agent work. "
                    "Returns health score, missing sections, validation/documentation/safety issues, and suggested additions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_chars": {
                            "type": "integer",
                            "minimum": 500,
                            "maximum": 50000,
                            "description": "Maximum characters of KAGENT.md content to inspect.",
                        },
                    },
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
                "name": "preview_rollback_session",
                "description": "Preview the current session's active rollbackable paths without applying changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200, "description": "Maximum number of active rollback records to scan."},
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "preview_rollback_paths",
                "description": "Preview rollback diffs for selected paths, optionally constrained to a rollback_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Workspace-relative paths to preview.",
                        },
                        "rollback_id": {"type": "integer", "minimum": 1, "description": "Optional rollback history id to inspect."},
                    },
                    "required": ["paths"],
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
        {
            "type": "function",
            "function": {
                "name": "rollback_paths",
                "description": "Rollback selected workspace paths, optionally constrained to a rollback_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Workspace-relative paths to rollback.",
                        },
                        "rollback_id": {"type": "integer", "minimum": 1, "description": "Optional rollback history id to restore from."},
                    },
                    "required": ["paths"],
                    "additionalProperties": False,
                },
            },
        },
    ]

