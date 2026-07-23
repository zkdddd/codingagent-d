from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_HISTORY = 20
REPEAT_THRESHOLD = 2


def tool_call_signature(name: str, args: dict[str, Any]) -> str:
    payload = {
        "name": name,
        "args": _normalized_args(name, args),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"{name}:{digest}"


def record_tool_call(
    history: list[dict[str, Any]],
    *,
    name: str,
    args: dict[str, Any],
    ok: bool,
    summary: str | None = None,
) -> dict[str, Any] | None:
    signature = tool_call_signature(name, args)
    entry = {
        "signature": signature,
        "name": name,
        "args": _normalized_args(name, args),
        "ok": bool(ok),
        "summary": summary,
    }
    history.append(entry)
    del history[:-MAX_HISTORY]
    return loop_warning(history, entry)


def loop_warning(history: list[dict[str, Any]], latest: dict[str, Any]) -> dict[str, Any] | None:
    same = [entry for entry in history if entry.get("signature") == latest.get("signature")]
    if len(same) < REPEAT_THRESHOLD:
        return None

    failed_count = sum(1 for entry in same if not bool(entry.get("ok")))
    if failed_count >= REPEAT_THRESHOLD:
        return _warning(
            latest,
            "repeated_failed_tool",
            "The same tool call has failed repeatedly. Do not retry it unchanged; gather different context or change the arguments.",
            len(same),
            failed_count,
        )

    if latest.get("name") in {"read_file", "search_file", "find_symbol", "list_files"} and len(same) >= 3:
        return _warning(
            latest,
            "repeated_inspection",
            "The same inspection tool call has repeated several times. Use the information already gathered or inspect a different target.",
            len(same),
            failed_count,
        )
    return None


def loop_warning_prompt(warning: dict[str, Any] | None) -> str:
    if not warning:
        return ""
    return (
        "Potential tool loop detected.\n"
        f"- category: {warning['category']}\n"
        f"- tool: {warning['tool']}\n"
        f"- repeat_count: {warning['repeat_count']}\n"
        f"- failed_count: {warning['failed_count']}\n"
        f"- guidance: {warning['guidance']}"
    )


def _normalized_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    keys_by_tool = {
        "read_file": ["path", "start_line", "end_line"],
        "search_file": ["query", "path", "file_glob", "case_sensitive"],
        "find_symbol": ["query", "kind", "exact"],
        "run_command": ["command", "cwd"],
        "apply_patch": ["patch"],
        "write_file": ["path"],
        "delete_path": ["path", "recursive"],
        "rename_path": ["source_path", "target_path"],
        "copy_path": ["source_path", "target_path"],
        "make_directory": ["path"],
    }
    keys = keys_by_tool.get(name)
    if not keys:
        keys = sorted(str(key) for key in args)
    normalized: dict[str, Any] = {}
    for key in keys:
        if key not in args:
            continue
        value = args[key]
        if key == "patch" and isinstance(value, str):
            normalized[key] = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
        else:
            normalized[key] = value
    return normalized


def _warning(
    latest: dict[str, Any],
    category: str,
    guidance: str,
    repeat_count: int,
    failed_count: int,
) -> dict[str, Any]:
    return {
        "category": category,
        "tool": latest.get("name"),
        "signature": latest.get("signature"),
        "repeat_count": repeat_count,
        "failed_count": failed_count,
        "guidance": guidance,
    }
