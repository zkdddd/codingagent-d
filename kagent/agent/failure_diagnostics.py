from __future__ import annotations

import re
from typing import Any

MAX_DIAGNOSTICS = 12


def extract_failure_diagnostics(result: dict[str, Any]) -> list[dict[str, Any]]:
    text = _combined_output(result)
    if not text.strip():
        return []

    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(_pytest_failures(text))
    diagnostics.extend(_python_tracebacks(text))
    diagnostics.extend(_syntax_errors(text))
    diagnostics.extend(_generic_file_lines(text))
    return _dedupe(diagnostics)[:MAX_DIAGNOSTICS]


def diagnostics_summary(diagnostics: list[dict[str, Any]]) -> str | None:
    if not diagnostics:
        return None
    lines = ["Failure locations:"]
    for item in diagnostics[:MAX_DIAGNOSTICS]:
        location = item.get("path") or item.get("nodeid") or "unknown"
        if item.get("line"):
            location = f"{location}:{item['line']}"
        label = item.get("kind") or "failure"
        detail = item.get("message")
        suffix = f" - {detail}" if detail else ""
        lines.append(f"- {label}: {location}{suffix}")
    return "\n".join(lines)


def _combined_output(result: dict[str, Any]) -> str:
    return "\n".join(
        str(result.get(key) or "")
        for key in ("stderr", "stdout", "error", "summary")
    )


def _pytest_failures(text: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for match in re.finditer(r"_{3,}\s+([^\n]+?)\s+_{3,}", text):
        node = match.group(1).strip()
        if not node or " " not in node and "::" not in node and not node.endswith(".py"):
            continue
        diagnostics.append(
            {
                "kind": "pytest_failure",
                "nodeid": node,
                "message": "pytest reported this failing test or case",
            }
        )

    for match in re.finditer(r"FAILED\s+([^\s]+?::[^\s]+)", text):
        diagnostics.append(
            {
                "kind": "pytest_failed_node",
                "nodeid": match.group(1).strip(),
                "message": "pytest failed node",
            }
        )
    return diagnostics


def _python_tracebacks(text: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    pattern = re.compile(r'File "([^"]+)", line (\d+)(?:, in ([^\n]+))?')
    for match in pattern.finditer(text):
        message = match.group(3).strip() if match.group(3) else None
        diagnostics.append(
            {
                "kind": "python_traceback",
                "path": _normalize_path(match.group(1)),
                "line": int(match.group(2)),
                "message": message,
            }
        )
    return diagnostics


def _syntax_errors(text: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if "SyntaxError:" not in line:
            continue
        previous_file = _nearest_file_line(lines[:idx])
        diagnostic = {
            "kind": "syntax_error",
            "message": line.strip(),
        }
        if previous_file:
            diagnostic.update(previous_file)
        diagnostics.append(diagnostic)
    return diagnostics


def _generic_file_lines(text: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    pattern = re.compile(r"(?P<path>[\w./\\:-]+\.py):(?P<line>\d+)(?::\d+)?:?\s*(?P<message>[^\n]*)")
    for match in pattern.finditer(text):
        diagnostics.append(
            {
                "kind": "file_line",
                "path": _normalize_path(match.group("path")),
                "line": int(match.group("line")),
                "message": match.group("message").strip() or None,
            }
        )
    return diagnostics


def _nearest_file_line(lines: list[str]) -> dict[str, Any] | None:
    pattern = re.compile(r'File "([^"]+)", line (\d+)')
    for line in reversed(lines[-8:]):
        match = pattern.search(line)
        if match:
            return {
                "path": _normalize_path(match.group(1)),
                "line": int(match.group(2)),
            }
    return None


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any, Any, Any]] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = (
            item.get("kind"),
            item.get("path"),
            item.get("line"),
            item.get("nodeid"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
