from __future__ import annotations

from typing import Any


CHANGE_TOOLS = {
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


def build_change_plan(
    name: str,
    args: dict[str, Any],
    *,
    preview: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if name not in CHANGE_TOOLS:
        return None

    files = _planned_paths(name, args)
    operation = _operation_for_tool(name)
    risk_level = str((policy or {}).get("risk_level") or "unknown")
    destructive = bool((policy or {}).get("destructive", False))
    approval_required = bool((policy or {}).get("approval_required", False))
    preview_text = preview or ""
    plan = {
        "tool": name,
        "operation": operation,
        "paths": files,
        "path_count": len(files),
        "target_summary": _target_summary(files),
        "intent": _intent_for_tool(name, files),
        "risk_level": risk_level,
        "risk_summary": _risk_summary(name, files, risk_level, destructive, approval_required),
        "destructive": destructive,
        "approval_required": approval_required,
        "summary": _summary(name, operation, files, destructive, approval_required),
        "validation_hint": _validation_hint(files),
        "preview_available": bool(preview_text.strip()),
        "preview_lines": len(preview_text.splitlines()) if preview_text else 0,
        "preview_truncated_for_plan": len(preview_text) > 2000,
    }
    if preview_text:
        plan["preview_excerpt"] = _clip(preview_text, 2000)
    return plan


def change_plan_for_log(plan: dict[str, Any]) -> dict[str, Any]:
    """Return the compact fields most useful for run-log timelines and UI review."""
    return {
        "summary": plan.get("summary"),
        "operation": plan.get("operation"),
        "paths": plan.get("paths") if isinstance(plan.get("paths"), list) else [],
        "intent": plan.get("intent"),
        "risk_summary": plan.get("risk_summary"),
        "validation_hint": plan.get("validation_hint"),
    }


def _planned_paths(name: str, args: dict[str, Any]) -> list[str]:
    if name == "apply_patch":
        paths = args.get("files_touched") or []
        return [str(path) for path in paths if path]
    if name in {"write_file", "delete_path", "make_directory"}:
        return [str(args["path"])] if args.get("path") else []
    if name in {"rename_path", "copy_path"}:
        return [
            str(path)
            for path in (args.get("source_path"), args.get("target_path"))
            if path
        ]
    if name in {"rollback_last_change", "rollback_change", "rollback_paths"}:
        paths = args.get("paths") or []
        return [str(path) for path in paths if path]
    return []


def _operation_for_tool(name: str) -> str:
    return {
        "write_file": "write",
        "apply_patch": "patch",
        "rename_path": "rename",
        "copy_path": "copy",
        "delete_path": "delete",
        "make_directory": "mkdir",
        "rollback_last_change": "rollback",
        "rollback_change": "rollback",
        "rollback_paths": "rollback",
    }.get(name, name)


def _target_summary(paths: list[str]) -> str:
    if not paths:
        return "workspace"
    if len(paths) == 1:
        return paths[0]
    preview = ", ".join(paths[:3])
    if len(paths) > 3:
        preview += f", ... ({len(paths)} paths)"
    return preview


def _intent_for_tool(name: str, paths: list[str]) -> str:
    target = _target_summary(paths)
    return {
        "write_file": f"Replace or create file content at {target}.",
        "apply_patch": f"Apply a targeted patch to {target}.",
        "rename_path": f"Rename or move {target}.",
        "copy_path": f"Copy {target}.",
        "delete_path": f"Remove {target}.",
        "make_directory": f"Create directory {target}.",
        "rollback_last_change": f"Restore the latest rollback state for {target}.",
        "rollback_change": f"Restore a selected rollback state for {target}.",
        "rollback_paths": f"Restore selected rollback paths for {target}.",
    }.get(name, f"Change {target}.")


def _risk_summary(
    name: str,
    paths: list[str],
    risk_level: str,
    destructive: bool,
    approval_required: bool,
) -> str:
    flags = [f"risk={risk_level}"]
    if destructive:
        flags.append("destructive")
    if approval_required:
        flags.append("approval required")
    if name in {"delete_path", "rollback_last_change", "rollback_change", "rollback_paths"}:
        flags.append("can remove or replace current workspace state")
    elif name in {"write_file", "apply_patch"}:
        flags.append("can change source content")
    elif name in {"rename_path", "copy_path", "make_directory"}:
        flags.append("can change workspace structure")
    if len(paths) > 1:
        flags.append(f"{len(paths)} paths")
    return "; ".join(flags)


def _validation_hint(paths: list[str]) -> str:
    suffixes = {str(path).lower().rsplit(".", 1)[-1] for path in paths if "." in str(path)}
    if "py" in suffixes:
        return "Run Python syntax checks, related tests for changed files, then full validation if available."
    if suffixes & {"js", "jsx", "ts", "tsx"}:
        return "Run the project's typecheck/lint/test script after the edit."
    if suffixes & {"md", "txt", "rst"}:
        return "Review rendered or textual documentation output; automated validation may be unnecessary."
    return "Run the smallest relevant project validation after the edit."


def _summary(
    name: str,
    operation: str,
    paths: list[str],
    destructive: bool,
    approval_required: bool,
) -> str:
    target = ", ".join(paths[:4]) if paths else "workspace"
    if len(paths) > 4:
        target += f", ... ({len(paths)} paths)"
    flags = []
    if destructive:
        flags.append("destructive")
    if approval_required:
        flags.append("requires approval")
    suffix = f" [{' / '.join(flags)}]" if flags else ""
    return f"Plan to {operation} via `{name}` on {target}.{suffix}"


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 28)].rstrip() + "\n... (plan preview clipped)"
