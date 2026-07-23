from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_CONTEXT_LINES = 40
MAX_FOCUS_TARGETS = 3


def focus_targets_from_diagnostics(
    diagnostics: list[dict[str, Any]],
    *,
    context_lines: int = DEFAULT_CONTEXT_LINES,
    max_targets: int = MAX_FOCUS_TARGETS,
    symbol_impacts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, int | None]] = set()
    for item in diagnostics:
        path = _diagnostic_path(item)
        if not path:
            continue
        line = _diagnostic_line(item)
        if line is not None:
            start_line = max(1, line - context_lines)
            end_line = line + context_lines
            reason = f"Focus around diagnostic line {line}"
        else:
            start_line = 1
            end_line = 160
            reason = "Focus on the failing test file or diagnostic file"

        key = (path, start_line, end_line)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
                "max_chars": 16000,
                "reason": reason,
                "diagnostic": item,
            }
        )
        if len(targets) >= max_targets:
            break
    for target in _symbol_focus_targets(symbol_impacts or [], diagnostics):
        key = (target["path"], target["start_line"], target["end_line"])
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)
        if len(targets) >= max_targets:
            break
    return targets


def focus_prompt(
    targets: list[dict[str, Any]],
    *,
    symbol_impacts: list[dict[str, Any]] | None = None,
) -> str:
    if not targets:
        return ""
    lines = [
        "Validation failed. I automatically read the most relevant failure locations.",
        "Use these focused excerpts first before searching broadly:",
    ]
    for idx, target in enumerate(targets, start=1):
        lines.append(
            f"{idx}. {target['path']}:{target['start_line']}-{target['end_line']} - {target['reason']}"
        )
    symbol_hints = symbol_repair_hints(symbol_impacts or [], targets)
    if symbol_hints:
        lines.append("Symbol impact repair hints:")
        lines.extend(f"- {hint}" for hint in symbol_hints)
    return "\n".join(lines)


def symbol_repair_hints(
    symbol_impacts: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    *,
    max_hints: int = 5,
) -> list[str]:
    target_paths = {_normalize_path(str(target.get("path") or "")) for target in targets}
    hints: list[str] = []
    for impact in symbol_impacts:
        if not isinstance(impact, dict):
            continue
        symbol = str(impact.get("symbol") or "").strip()
        definition = str(impact.get("definition_path") or "").strip()
        related_tests = impact.get("related_tests") if isinstance(impact.get("related_tests"), list) else []
        related_test_set = {_normalize_path(str(path)) for path in related_tests if path}
        matches_failure = bool(target_paths.intersection(related_test_set))
        if not symbol:
            continue
        if matches_failure:
            hints.append(
                f"Failing test covers changed symbol `{symbol}`; inspect `{definition}` and the failing related test before broad search."
            )
        elif definition:
            hints.append(
                f"Changed symbol `{symbol}` is defined at `{definition}`; keep fixes scoped to this symbol unless diagnostics point elsewhere."
            )
        if len(hints) >= max_hints:
            break
    return hints


def _diagnostic_path(item: dict[str, Any]) -> str | None:
    path = item.get("path")
    if path:
        return str(path)
    nodeid = item.get("nodeid")
    if not nodeid:
        return None
    raw_path = str(nodeid).split("::", 1)[0]
    if Path(raw_path).suffix:
        return raw_path
    return None


def _diagnostic_line(item: dict[str, Any]) -> int | None:
    try:
        line = item.get("line")
        return int(line) if line else None
    except (TypeError, ValueError):
        return None


def _symbol_focus_targets(
    symbol_impacts: list[dict[str, Any]], diagnostics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    diagnostic_paths = {
        _normalize_path(path)
        for path in (_diagnostic_path(item) for item in diagnostics)
        if path
    }
    targets: list[dict[str, Any]] = []
    for impact in symbol_impacts:
        if not isinstance(impact, dict):
            continue
        definition = str(impact.get("definition_path") or "").strip()
        if not definition:
            continue
        related_tests = impact.get("related_tests") if isinstance(impact.get("related_tests"), list) else []
        related_test_set = {_normalize_path(str(path)) for path in related_tests if path}
        if related_test_set and not diagnostic_paths.intersection(related_test_set):
            continue
        symbol = str(impact.get("symbol") or "symbol")
        targets.append(
            {
                "path": definition,
                "start_line": 1,
                "end_line": 220,
                "max_chars": 20000,
                "reason": f"Inspect changed symbol `{symbol}` because a related validation target failed",
                "symbol": symbol,
            }
        )
    return targets


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()
