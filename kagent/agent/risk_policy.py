from __future__ import annotations

import re
from pathlib import Path
from typing import Any

RISK_LEVELS = ("safe", "low", "medium", "high", "critical")
RISK_LABELS = {
    "safe": "Safe",
    "low": "Low risk",
    "medium": "Medium risk",
    "high": "High risk",
    "critical": "Critical",
}
INSPECTION_TOOLS = {
    "list_files",
    "search_file",
    "read_file",
    "list_rollback_history",
    "preview_rollback_change",
    "preview_rollback_session",
    "preview_rollback_paths",
}
SENSITIVE_PATH_NAMES = {
    ".env",
    ".gitignore",
    "main.py",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "go.sum",
}
SENSITIVE_PATH_PARTS = {
    ".git",
    ".github",
    ".vscode",
    ".idea",
}
SAFE_COMMAND_PATTERNS = (
    r"(^| )dir( |$)",
    r"(^| )ls( |$)",
    r"(^| )pwd( |$)",
    r"(^| )rg( |$)",
    r"(^| )git status( |$)",
    r"(^| )git diff( |$)",
    r"(^| )type( |$)",
    r"(^| )cat( |$)",
    r"(^| )get-content( |$)",
    r"(^| )python(?:\.exe)? -m py_compile( |$)",
    r"(^| )python(?:\.exe)? -m pytest( |$)",
    r"-m py_compile( |$)",
    r"-m pytest( |$)",
    r"(^| )pytest( |$)",
    r"(^| )ruff check( |$)",
    r"(^| )mypy( |$)",
    r"(^| )(npm|pnpm|yarn) (run )?(lint|test|typecheck|build)( |$)",
    r"(^| )cargo test( |$)",
    r"(^| )go test( |$)",
)
NETWORK_COMMAND_PATTERNS = (
    "curl ",
    "wget ",
    "Invoke-WebRequest".lower(),
    "iwr ",
    "Invoke-RestMethod".lower(),
    "irm ",
    "ssh ",
    "scp ",
    "rsync ",
)
CRITICAL_COMMAND_PATTERNS = (
    "rm -rf",
    "rm -r ",
    "del /f",
    "del /q",
    "erase /f",
    "rd /s",
    "rmdir /s",
    "remove-item -recurse",
    "remove-item -force",
    "git reset --hard",
    "git clean -fd",
    "format ",
    "shutdown ",
)
HIGH_RISK_COMMAND_PATTERNS = (
    "git push",
    "git commit",
    "git merge",
    "git rebase",
    "pip install",
    "pip uninstall",
    "npm install",
    "npm uninstall",
    "pnpm install",
    "pnpm remove",
    "yarn add",
    "yarn remove",
    "set-content ",
    "add-content ",
    "out-file ",
    "start-process ",
)
DEPENDENCY_COMMAND_PATTERNS = (
    "pip install",
    "pip uninstall",
    "python -m pip install",
    "python -m pip uninstall",
    "npm install",
    "npm uninstall",
    "pnpm install",
    "pnpm remove",
    "yarn add",
    "yarn remove",
    "cargo add",
    "cargo install",
    "go get",
)
GIT_WRITE_COMMAND_PATTERNS = (
    "git push",
    "git commit",
    "git merge",
    "git rebase",
    "git reset",
    "git clean",
    "git checkout ",
    "git switch ",
    "git restore ",
    "git stash",
    "git tag",
)


def tool_policy(
    name: str,
    args: dict[str, Any],
    display_args: dict[str, Any],
    preview_text: str | None,
) -> dict[str, Any]:
    if name in INSPECTION_TOOLS:
        return _build_tool_policy(
            level="safe",
            approval_required=False,
            reason="This tool only reads workspace state.",
        )

    if name == "run_command":
        return _command_tool_policy(args, display_args)

    if name == "apply_patch":
        patch_info = display_args if isinstance(display_args, dict) else {}
        files_touched = [str(path) for path in patch_info.get("files_touched", [])]
        file_count = int(patch_info.get("file_count", 0) or 0)
        added, removed = _patch_change_counts(str(preview_text or args.get("patch") or ""))
        total_changed_lines = added + removed
        if any(_is_sensitive_path(path) for path in files_touched):
            return _build_tool_policy(
                level="high",
                reason="This patch touches a sensitive project or environment file.",
            )
        if file_count >= 5 or total_changed_lines >= 200:
            return _build_tool_policy(
                level="high",
                reason=f"This patch changes {file_count} files and about {total_changed_lines} lines.",
            )
        if file_count >= 3 or total_changed_lines >= 80:
            return _build_tool_policy(
                level="medium",
                reason=f"This patch changes multiple files or a larger diff ({total_changed_lines} lines).",
            )
        return _build_tool_policy(
            level="low",
            approval_required=False,
            reason=f"This is a focused patch ({file_count} file, about {total_changed_lines} changed lines).",
        )

    if name == "write_file":
        path = str(display_args.get("path") or args.get("path") or "")
        exists = bool(display_args.get("exists", False))
        line_count = int(display_args.get("line_count", 0) or 0)
        if _is_sensitive_path(path):
            return _build_tool_policy(
                level="high",
                reason=f"This overwrites sensitive file `{path}`.",
            )
        if exists and line_count >= 200:
            return _build_tool_policy(
                level="high",
                reason=f"This fully overwrites existing file `{path}` with {line_count} lines.",
            )
        if exists:
            return _build_tool_policy(
                level="medium",
                reason=f"This fully overwrites existing file `{path}`.",
            )
        return _build_tool_policy(
            level="low",
            approval_required=False,
            reason=f"This creates a new file `{path}`.",
        )

    if name == "rename_path":
        source_path = str(display_args.get("source_path") or args.get("source_path") or "")
        target_path = str(display_args.get("target_path") or args.get("target_path") or "")
        item_type = str(display_args.get("item_type") or "item")
        if item_type == "directory":
            return _build_tool_policy(
                level="high",
                reason=f"This renames a directory: `{source_path}` -> `{target_path}`.",
            )
        if _is_sensitive_path(source_path) or _is_sensitive_path(target_path):
            return _build_tool_policy(
                level="high",
                reason="This rename touches a sensitive path.",
            )
        return _build_tool_policy(
            level="medium",
            reason=f"This renames file `{source_path}` -> `{target_path}`.",
        )

    if name == "copy_path":
        source_path = str(display_args.get("source_path") or args.get("source_path") or "")
        target_path = str(display_args.get("target_path") or args.get("target_path") or "")
        item_type = str(display_args.get("item_type") or "item")
        item_count = int(display_args.get("item_count", 0) or 0)
        if item_type == "directory" or item_count >= 50:
            return _build_tool_policy(
                level="medium",
                reason=f"This copies a larger tree from `{source_path}` to `{target_path}`.",
            )
        return _build_tool_policy(
            level="low",
            approval_required=False,
            reason=f"This copies `{source_path}` to `{target_path}`.",
        )

    if name == "delete_path":
        path = str(display_args.get("path") or args.get("path") or "")
        item_type = str(display_args.get("item_type") or "item")
        item_count = int(display_args.get("item_count", 0) or 0)
        if item_type == "directory" and (item_count >= 20 or _is_sensitive_path(path)):
            return _build_tool_policy(
                level="critical",
                destructive=True,
                reason=f"This deletes directory `{path}` with {item_count} items.",
            )
        return _build_tool_policy(
            level="high",
            destructive=True,
            reason=f"This deletes {item_type} `{path}`.",
        )

    if name == "make_directory":
        path = str(display_args.get("path") or args.get("path") or "")
        if _is_sensitive_path(path):
            return _build_tool_policy(
                level="medium",
                reason=f"This creates or reuses a sensitive directory path `{path}`.",
            )
        return _build_tool_policy(
            level="low",
            approval_required=False,
            reason=f"This creates directory `{path}`.",
        )

    if name in {"rollback_last_change", "rollback_change", "rollback_paths"}:
        path_count = int(display_args.get("path_count", 0) or 0)
        superseded = int(display_args.get("superseded_active_count", 0) or 0)
        if superseded > 0 or path_count >= 4:
            return _build_tool_policy(
                level="medium",
                reason="This rollback can replace several newer workspace changes.",
            )
        return _build_tool_policy(
            level="low",
            approval_required=False,
            reason="This rollback restores the last recorded workspace state.",
        )

    return _build_tool_policy(
        level="medium",
        reason="This tool changes workspace state.",
    )


def _risk_rank(level: str) -> int:
    try:
        return RISK_LEVELS.index(str(level).strip().lower())
    except ValueError:
        return RISK_LEVELS.index("medium")


def _build_tool_policy(
    *,
    level: str,
    reason: str,
    destructive: bool = False,
    approval_required: bool | None = None,
    categories: list[str] | None = None,
    factors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    normalized = str(level or "medium").strip().lower()
    if normalized not in RISK_LEVELS:
        normalized = "medium"
    if approval_required is None:
        approval_required = destructive or _risk_rank(normalized) >= _risk_rank("medium")
    return {
        "risk_level": normalized,
        "risk_label": RISK_LABELS.get(normalized, normalized.title()),
        "approval_required": bool(approval_required),
        "destructive": bool(destructive),
        "reason": reason.strip() or "This action changes the workspace.",
        "risk_categories": _dedupe_strings(categories or []),
        "risk_factors": factors or [],
    }


def _is_sensitive_path(raw_path: str) -> bool:
    path = Path(str(raw_path or ""))
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if name in SENSITIVE_PATH_NAMES:
        return True
    if name.startswith(".env"):
        return True
    return bool(parts & SENSITIVE_PATH_PARTS)


def _patch_change_counts(patch: str) -> tuple[int, int]:
    added = 0
    removed = 0
    for line in str(patch or "").splitlines():
        if line.startswith(("diff --git ", "index ", "@@ ", "+++ ", "--- ")):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def _normalize_command(command: str) -> str:
    return " ".join(str(command or "").strip().lower().split())


def _command_tool_policy(args: dict[str, Any], display_args: dict[str, Any]) -> dict[str, Any]:
    command = str(display_args.get("command") or args.get("command") or "")
    cwd = str(display_args.get("cwd") or args.get("cwd") or ".")
    normalized = _normalize_command(command)
    categories: list[str] = []
    factors: list[dict[str, str]] = []
    if not normalized:
        return _build_tool_policy(
            level="medium",
            reason="This command could not be classified.",
            categories=["unknown_command"],
        )

    for pattern in CRITICAL_COMMAND_PATTERNS:
        if pattern in normalized:
            return _build_tool_policy(
                level="critical",
                destructive=True,
                reason=f"This command includes a destructive shell pattern: `{pattern}`.",
                categories=["destructive_delete"],
                factors=[_factor("destructive_pattern", pattern)],
            )

    if re.search(r"(^| )(del|erase|rm|rd|rmdir|remove-item)( |$)", normalized):
        return _build_tool_policy(
            level="critical",
            destructive=True,
            reason="This command may delete files or folders.",
            categories=["destructive_delete"],
            factors=[_factor("delete_command", command)],
        )

    if any(token in normalized for token in ("&&", "||", ";")):
        categories.append("chained_shell")
        factors.append(_factor("shell_chain", "Command uses shell chaining."))
        return _build_tool_policy(
            level="high",
            reason="This is a chained shell command, which is harder to predict and review.",
            categories=categories,
            factors=factors,
        )

    if any(token in normalized for token in (">", ">>")):
        categories.append("redirection")
        factors.append(_factor("shell_redirection", "Command writes through shell redirection."))
        return _build_tool_policy(
            level="high",
            reason="This command writes output through shell redirection.",
            categories=categories,
            factors=factors,
        )

    for pattern in DEPENDENCY_COMMAND_PATTERNS:
        if pattern in normalized:
            return _build_tool_policy(
                level="high",
                reason=f"This command changes installed dependencies or the environment: `{pattern}`.",
                categories=["dependency_change"],
                factors=[_factor("dependency_command", pattern)],
            )

    for pattern in GIT_WRITE_COMMAND_PATTERNS:
        if pattern in normalized:
            return _build_tool_policy(
                level="high",
                reason=f"This command changes Git repository state: `{pattern}`.",
                categories=["git_write"],
                factors=[_factor("git_write_command", pattern)],
            )

    for pattern in NETWORK_COMMAND_PATTERNS:
        if pattern in normalized:
            return _build_tool_policy(
                level="high",
                reason=f"This command can access the network: `{pattern}`.",
                categories=["network"],
                factors=[_factor("network_command", pattern)],
            )

    for pattern in HIGH_RISK_COMMAND_PATTERNS:
        if pattern in normalized:
            return _build_tool_policy(
                level="high",
                reason=f"This command changes the environment or repository state: `{pattern}`.",
                categories=["state_change"],
                factors=[_factor("high_risk_pattern", pattern)],
            )

    for pattern in SAFE_COMMAND_PATTERNS:
        if re.search(pattern, normalized):
            category = "validation" if _looks_like_validation_command(normalized) else "read_only"
            return _build_tool_policy(
                level="low",
                approval_required=False,
                reason=f"This looks like a read-only or validation command in `{cwd}`.",
                categories=[category],
                factors=[_factor("safe_pattern", pattern)],
            )

    return _build_tool_policy(
        level="medium",
        reason=f"This command runs arbitrary shell code in `{cwd}` and should be reviewed once.",
        categories=["arbitrary_shell"],
        factors=[_factor("unclassified_command", command)],
    )


def _factor(kind: str, detail: str) -> dict[str, str]:
    return {"kind": kind, "detail": detail}


def _looks_like_validation_command(normalized: str) -> bool:
    validation_terms = (
        "pytest",
        "py_compile",
        "compileall",
        "ruff",
        "mypy",
        "lint",
        "test",
        "typecheck",
        "build",
        "cargo test",
        "go test",
    )
    return any(term in normalized for term in validation_terms)


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
