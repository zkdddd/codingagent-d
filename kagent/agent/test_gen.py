from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .project_map import build_project_map
from .symbol_index import build_symbol_index

# Symbol kinds worth generating a test scaffold for (skip imports/consts/etc).
_TESTABLE_KINDS = {"class", "function", "method"}
# Skip dunder and private-by-convention symbols — they are usually internal.
_SKIP_NAMES = {"__init__", "__main__", "__all__", "__repr__", "__str__", "__eq__"}


def find_untested_symbols(
    root: Path,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return symbols that live in a source file with no mapped test file.

    Uses the project_map source->test mapping for a fast file-level coverage
    check (O(project size), not O(symbols x references)), so a symbol counts
    as "untested" when its defining file has no corresponding test file. This
    is the same `related_test_count == 0` signal symbol_change_plan computes
    per-symbol, but evaluated across the whole project at once.
    """
    root = Path(root)
    project_map = build_project_map(root)
    source_to_tests = project_map.source_to_tests
    symbols = [s for s in build_symbol_index(root) if s.kind in _TESTABLE_KINDS]

    untested: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for symbol in symbols:
        if symbol.path.endswith("test_") or "/tests/" in symbol.path:
            continue
        if symbol.name in _SKIP_NAMES or symbol.name.startswith("_"):
            continue
        key = (symbol.path, symbol.line)
        if key in seen:
            continue
        tests = source_to_tests.get(symbol.path) or []
        if tests:
            continue
        seen.add(key)
        untested.append(
            {
                "symbol": symbol.name,
                "kind": symbol.kind,
                "path": symbol.path,
                "line": symbol.line,
                "container": symbol.container,
                "module": symbol.module,
                "suggested_test_path": _suggested_test_path(symbol.path),
            }
        )
        if len(untested) >= limit:
            break
    return untested


def generate_test_scaffold(
    root: Path,
    symbol_info: dict[str, Any],
) -> dict[str, Any]:
    """Generate a pytest scaffold for an untested symbol.

    Returns the suggested test file path and its content: an import of the
    module under test plus one parametrizable placeholder test per testable
    top-level symbol found in that module. The scaffold is intentionally
    minimal (a real assertion is left as a TODO) so a human or the agent fills
    in the expected behavior — generating fake assertions risks false confidence.
    """
    root = Path(root)
    rel_source = str(symbol_info.get("path") or "")
    if not rel_source:
        return {"ok": False, "error": "source path is required"}

    source_path = root / rel_source
    if not source_path.exists():
        return {"ok": False, "error": f"source not found: {rel_source}"}

    module_dotpath = _module_dotpath(rel_source)
    test_path = _suggested_test_path(rel_source)
    testable = _testable_symbols_in_file(source_path)
    # Prefer the requested symbol first, then other testable symbols in the file.
    requested = str(symbol_info.get("symbol") or "")
    ordered = []
    for sym in testable:
        if sym["name"] == requested:
            ordered.insert(0, sym)
        else:
            ordered.append(sym)
    seen = set()
    targets: list[dict[str, Any]] = []
    for sym in ordered:
        if sym["name"] in seen:
            continue
        seen.add(sym["name"])
        targets.append(sym)
    if not targets:
        targets = [{"name": requested or "symbol", "kind": "function", "signature": ""}]

    content = _render_scaffold(module_dotpath, targets, requested)
    return {
        "ok": True,
        "source_path": rel_source,
        "test_path": test_path,
        "module": module_dotpath,
        "targets": [t["name"] for t in targets],
        "content": content,
    }


def _render_scaffold(
    module_dotpath: str,
    targets: list[dict[str, Any]],
    requested: str,
) -> str:
    lines = [
        '"""Auto-generated test scaffold for kagent test generation.',
        "",
        f"Targets: {', '.join(t['name'] for t in targets)}",
        "Replace the placeholder assertions with the expected behavior.",
        '"""',
        "import pytest",
        "",
        f"from {module_dotpath} import {', '.join(t['name'] for t in targets)}",
        "",
        "",
    ]
    for target in targets:
        name = target["name"]
        lines.append(f"def test_{name}():")
        lines.append(f'    """Smoke test for `{name}` — replace with real assertions."""')
        lines.append(f"    # TODO: assert expected behavior of {name}")
        lines.append("    assert True  # placeholder — remove once real assertions exist")
        lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _testable_symbols_in_file(path: Path) -> list[dict[str, Any]]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    symbols: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and node.name not in {"__init__"}:
                continue
            symbols.append({"name": node.name, "kind": "function", "signature": ""})
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            symbols.append({"name": node.name, "kind": "class", "signature": ""})
    return symbols


def _suggested_test_path(source_path: str) -> str:
    rel = Path(str(source_path).replace("\\", "/"))
    if rel.parts and rel.parts[0] == "tests":
        return rel.as_posix()
    stem = rel.stem
    if rel.parts and rel.parts[0] in {"kagent", "src", "app"}:
        module_parts = list(rel.parts[1:])
        if module_parts:
            module_stem = Path(*module_parts).with_suffix("")
            return (Path("tests") / module_stem.parent / f"test_{module_stem.name}.py").as_posix()
    return (Path("tests") / f"test_{stem}.py").as_posix()


def _module_dotpath(source_path: str) -> str:
    rel = Path(str(source_path).replace("\\", "/"))
    parts = [p for p in rel.parts if p != "tests"]
    # Only strip common src-layout roots; `kagent` is a real package name, keep it.
    if parts and parts[0] in {"src", "app"}:
        parts = parts[1:]
    module = ".".join(parts).replace(".py", "")
    return module or rel.stem
