from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .project_map import build_project_map, related_tests_for_source

MAX_RELATED_TEST_COMMANDS = 3


def related_test_commands_for_changes(
    changed_paths: set[str],
    *,
    workspace_root: Path,
    cwd: str = ".",
    max_commands: int = MAX_RELATED_TEST_COMMANDS,
) -> list[dict[str, Any]]:
    tests = related_tests_for_changes(changed_paths, workspace_root=workspace_root)
    commands: list[dict[str, Any]] = []
    for test_path in tests[:max_commands]:
        commands.append(
            {
                "label": "Related tests",
                "reason": "Run tests inferred from the changed file path before the full suite.",
                "command": subprocess.list2cmdline([sys.executable, "-m", "pytest", "-q", test_path]),
                "cwd": cwd,
                "timeout_ms": 180000,
                "related_test": test_path,
            }
        )
    return commands


def related_tests_for_changes(changed_paths: set[str], *, workspace_root: Path) -> list[str]:
    project_map = build_project_map(workspace_root)
    test_set = set(project_map.test_files)
    related_by_source = project_map.source_to_tests
    candidates: list[str] = []
    seen: set[str] = set()
    for raw_path in sorted(path for path in changed_paths if path):
        normalized = Path(str(raw_path).replace("\\", "/")).as_posix()
        direct_tests = [normalized] if normalized in test_set else []
        mapped_tests = related_by_source.get(normalized)
        if mapped_tests is None:
            mapped_tests = related_tests_for_source(normalized, list(test_set))
        for candidate in [*direct_tests, *mapped_tests]:
            if candidate not in test_set:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
        for candidate in reference_related_tests(normalized, workspace_root=workspace_root):
            if candidate not in test_set:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def reference_related_tests(changed_path: str, *, workspace_root: Path) -> list[str]:
    impact = analyze_reference_impact(changed_path, workspace_root=workspace_root)
    return [item["path"] for item in impact["related_tests"]]


def analyze_reference_impact(changed_path: str, *, workspace_root: Path) -> dict[str, Any]:
    normalized = Path(str(changed_path).replace("\\", "/")).as_posix()
    if Path(normalized).suffix.lower() != ".py":
        return {"changed_path": normalized, "module": None, "symbols": [], "references": [], "related_tests": []}

    project_map = build_project_map(workspace_root)
    py_files = [
        path
        for path in [*project_map.source_files, *project_map.test_files]
        if Path(path).suffix.lower() == ".py"
    ]
    test_set = set(project_map.test_files)
    changed_module = _module_name_from_path(normalized)
    changed_symbols = _top_level_symbol_names(workspace_root / normalized)
    references: dict[str, _ReferenceMatch] = {}

    for rel_path in py_files:
        if rel_path == normalized:
            continue
        match = _references_in_file(
            workspace_root / rel_path,
            rel_path=rel_path,
            changed_module=changed_module,
            changed_symbols=changed_symbols,
        )
        if match is not None:
            references[rel_path] = match

    related: list[dict[str, str]] = []
    seen_tests: set[str] = set()
    for rel_path, match in sorted(references.items()):
        if rel_path in test_set:
            _append_related_test(related, seen_tests, rel_path, "references changed module or symbol")
            continue
        for test_path in project_map.source_to_tests.get(rel_path) or related_tests_for_source(
            rel_path, list(test_set)
        ):
            _append_related_test(
                related,
                seen_tests,
                test_path,
                f"covers referencing source {rel_path}",
            )

    return {
        "changed_path": normalized,
        "module": changed_module,
        "symbols": sorted(changed_symbols),
        "references": [
            {
                "path": match.path,
                "reasons": sorted(match.reasons),
                "lines": sorted(match.lines),
            }
            for match in sorted(references.values(), key=lambda item: item.path)
        ],
        "related_tests": related,
    }


@dataclass
class _ReferenceMatch:
    path: str
    reasons: set[str] = field(default_factory=set)
    lines: set[int] = field(default_factory=set)

    def add(self, reason: str, line: int | None) -> None:
        self.reasons.add(reason)
        if line:
            self.lines.add(line)


class _ReferenceVisitor(ast.NodeVisitor):
    def __init__(self, *, rel_path: str, changed_module: str, changed_symbols: set[str]):
        self.match = _ReferenceMatch(rel_path)
        self.changed_module = changed_module
        self.changed_symbols = changed_symbols

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if _module_matches(alias.name, self.changed_module):
                self.match.add(f"imports {alias.name}", node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        imported_names = {alias.name for alias in node.names}
        if _module_matches(module, self.changed_module):
            self.match.add(f"imports from {module}", node.lineno)
        parent = self.changed_module.rsplit(".", 1)[0] if "." in self.changed_module else ""
        leaf = self.changed_module.rsplit(".", 1)[-1]
        if module == parent and leaf in imported_names:
            self.match.add(f"imports module {leaf}", node.lineno)
        if module == self.changed_module and imported_names & self.changed_symbols:
            names = ", ".join(sorted(imported_names & self.changed_symbols))
            self.match.add(f"imports symbols {names}", node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.changed_symbols:
            self.match.add(f"references symbol {node.id}", node.lineno)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in self.changed_symbols:
            self.match.add(f"references attribute {node.attr}", node.lineno)
        self.generic_visit(node)


def _references_in_file(
    path: Path,
    *,
    rel_path: str,
    changed_module: str,
    changed_symbols: set[str],
) -> _ReferenceMatch | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
    visitor = _ReferenceVisitor(
        rel_path=rel_path,
        changed_module=changed_module,
        changed_symbols=changed_symbols,
    )
    visitor.visit(tree)
    return visitor.match if visitor.match.reasons else None


def _top_level_symbol_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if len(node.name) >= 3 and not node.name.startswith("__"):
                names.add(node.name)
    return names


def _module_name_from_path(path: str) -> str:
    return Path(path).with_suffix("").as_posix().replace("/", ".")


def _module_matches(candidate: str, changed_module: str) -> bool:
    return candidate == changed_module or candidate.startswith(f"{changed_module}.")


def _append_related_test(
    related: list[dict[str, str]], seen: set[str], path: str, reason: str
) -> None:
    if path in seen:
        return
    seen.add(path)
    related.append({"path": path, "reason": reason})
