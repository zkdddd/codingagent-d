from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from .symbol_index import find_symbol_contexts, find_symbol_references, find_symbols


def build_symbol_change_plan(
    root: Path,
    symbol_name: str,
    *,
    kind: str | None = None,
    exact: bool = True,
    context_lines: int = 4,
    max_references: int = 80,
    max_validation_commands: int = 5,
) -> dict[str, Any]:
    symbol = str(symbol_name or "").strip()
    if not symbol:
        return {"ok": False, "error": "symbol_name is required"}

    definitions = find_symbols(root, symbol, kind=kind, exact=exact, limit=10)
    contexts = find_symbol_contexts(
        root,
        symbol,
        kind=kind,
        exact=exact,
        limit=5,
        context_lines=context_lines,
        max_chars=10000,
    )
    references = find_symbol_references(root, symbol, include_tests=True, limit=max_references)
    related_tests = _related_tests_from_references(references)
    validation_commands = _validation_commands_for_tests(
        related_tests,
        max_commands=max_validation_commands,
    )
    impact_summary = _impact_summary(definitions, references, related_tests)

    return {
        "ok": True,
        "symbol": symbol,
        "kind": kind,
        "exact": exact,
        "definition_count": len(definitions),
        "definitions": definitions,
        "primary_definition": definitions[0] if definitions else None,
        "contexts": contexts,
        "reference_count": len(references),
        "references": references,
        "impact_summary": impact_summary,
        "risk_level": impact_summary["risk_level"],
        "impact_score": impact_summary["impact_score"],
        "related_tests": related_tests,
        "validation_commands": validation_commands,
        "risk_summary": _risk_summary(symbol, definitions, references, related_tests, impact_summary),
        "summary": _summary(symbol, definitions, references, related_tests),
    }


def _related_tests_from_references(references: list[dict[str, object]]) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []
    seen: set[str] = set()
    for reference in references:
        if not reference.get("is_test"):
            continue
        path = str(reference.get("path") or "")
        if not path or path in seen:
            continue
        seen.add(path)
        related.append(
            {
                "path": path,
                "reason": f"references symbol `{reference.get('symbol')}`",
                "first_reference_line": reference.get("line"),
                "reference_type": reference.get("reference_type"),
            }
        )
    return related


def _validation_commands_for_tests(
    related_tests: list[dict[str, Any]], *, max_commands: int
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for item in related_tests[:max_commands]:
        path = str(item.get("path") or "")
        if not path:
            continue
        commands.append(
            {
                "label": "Related symbol test",
                "reason": item.get("reason") or "Test references the changed symbol.",
                "command": subprocess.list2cmdline([sys.executable, "-m", "pytest", "-q", path]),
                "cwd": ".",
                "timeout_ms": 180000,
                "related_test": path,
            }
        )
    return commands


def _impact_summary(
    definitions: list[dict[str, object]],
    references: list[dict[str, object]],
    related_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    definition_paths = _unique_strings(str(item.get("path") or "") for item in definitions)
    production_files = _unique_strings(
        str(item.get("path") or "") for item in references if not item.get("is_test")
    )
    test_files = _unique_strings(
        str(item.get("path") or "") for item in references if item.get("is_test")
    )
    reference_types: dict[str, int] = {}
    for reference in references:
        ref_type = str(reference.get("reference_type") or "unknown")
        reference_types[ref_type] = reference_types.get(ref_type, 0) + 1

    production_reference_count = sum(1 for item in references if not item.get("is_test"))
    test_reference_count = sum(1 for item in references if item.get("is_test"))
    affected_file_count = len(set(production_files + test_files + definition_paths))
    impact_score = _impact_score(
        definition_count=len(definitions),
        production_reference_count=production_reference_count,
        test_reference_count=test_reference_count,
        affected_file_count=affected_file_count,
        related_test_count=len(related_tests),
    )
    return {
        "risk_level": _risk_level(impact_score),
        "impact_score": impact_score,
        "definition_paths": definition_paths,
        "production_files": production_files,
        "test_files": test_files,
        "affected_file_count": affected_file_count,
        "production_reference_count": production_reference_count,
        "test_reference_count": test_reference_count,
        "related_test_count": len(related_tests),
        "reference_types": dict(sorted(reference_types.items())),
    }


def _impact_score(
    *,
    definition_count: int,
    production_reference_count: int,
    test_reference_count: int,
    affected_file_count: int,
    related_test_count: int,
) -> int:
    score = 0
    if definition_count == 0:
        score += 25
    elif definition_count > 1:
        score += 15
    score += min(35, production_reference_count * 4)
    score += min(20, affected_file_count * 3)
    score += min(12, test_reference_count * 2)
    if production_reference_count and related_test_count == 0:
        score += 15
    return min(100, score)


def _risk_level(score: int) -> str:
    if score >= 65:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _unique_strings(values: object) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _risk_summary(
    symbol: str,
    definitions: list[dict[str, object]],
    references: list[dict[str, object]],
    related_tests: list[dict[str, Any]],
    impact_summary: dict[str, Any],
) -> str:
    parts = [
        f"{impact_summary.get('risk_level')} risk",
        f"impact score {impact_summary.get('impact_score')}",
        f"Changing `{symbol}` may affect {len(references)} reference(s)",
        f"{impact_summary.get('affected_file_count')} affected file(s)",
        f"{len(related_tests)} related test file(s)",
    ]
    if not definitions:
        parts.append("definition not found")
    if any(not item.get("is_test") for item in references):
        parts.append("non-test callers present")
    return "; ".join(parts)


def _summary(
    symbol: str,
    definitions: list[dict[str, object]],
    references: list[dict[str, object]],
    related_tests: list[dict[str, Any]],
) -> str:
    if not definitions:
        return f"No definition found for `{symbol}`; inspect references before editing."
    definition = definitions[0]
    location = f"{definition.get('path')}:{definition.get('line')}"
    return (
        f"Plan symbol change for `{symbol}` at {location}: "
        f"{len(references)} reference(s), {len(related_tests)} related test file(s)."
    )
