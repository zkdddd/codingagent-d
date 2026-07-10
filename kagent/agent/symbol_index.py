from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .project_map import build_project_map


SymbolKind = Literal[
    "class",
    "function",
    "method",
    "import",
    "interface",
    "struct",
    "enum",
    "type",
    "trait",
    "const",
]


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: SymbolKind
    path: str
    line: int
    end_line: int | None = None
    container: str | None = None
    module: str | None = None


def build_symbol_index(root: Path) -> list[Symbol]:
    project_map = build_project_map(root)
    symbols: list[Symbol] = []
    for rel_path in project_map.source_files:
        path = root / rel_path
        symbols.extend(_symbols_from_file(path, rel_path))
    return sorted(symbols, key=lambda item: (item.path, item.line, item.name))


def find_symbols(
    root: Path,
    query: str,
    *,
    kind: SymbolKind | None = None,
    exact: bool = True,
    limit: int = 50,
) -> list[dict[str, object]]:
    needle = str(query or "").strip()
    if not needle:
        return []
    matches: list[Symbol] = []
    for symbol in build_symbol_index(root):
        if kind and symbol.kind != kind:
            continue
        if exact and symbol.name != needle:
            continue
        if not exact and needle.lower() not in symbol.name.lower():
            continue
        matches.append(symbol)
        if len(matches) >= limit:
            break
    return [symbol_to_dict(symbol) for symbol in matches]


def symbol_to_dict(symbol: Symbol) -> dict[str, object]:
    return {
        "name": symbol.name,
        "kind": symbol.kind,
        "path": symbol.path,
        "line": symbol.line,
        "end_line": symbol.end_line,
        "container": symbol.container,
        "module": symbol.module,
    }


def _symbols_from_tree(tree: ast.AST, rel_path: str) -> list[Symbol]:
    visitor = _SymbolVisitor(rel_path)
    visitor.visit(tree)
    return visitor.symbols


def _symbols_from_file(path: Path, rel_path: str) -> list[Symbol]:
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if suffix == ".py":
        try:
            return _symbols_from_tree(ast.parse(text), rel_path)
        except SyntaxError:
            return []
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return _symbols_from_javascript_like(text, rel_path)
    if suffix == ".go":
        return _symbols_from_go(text, rel_path)
    if suffix == ".rs":
        return _symbols_from_rust(text, rel_path)
    if suffix == ".java":
        return _symbols_from_java(text, rel_path)
    return []


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str):
        self.rel_path = rel_path
        self.symbols: list[Symbol] = []
        self.containers: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append(
            Symbol(
                name=node.name,
                kind="class",
                path=self.rel_path,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", None),
                container=self._container(),
            )
        )
        self.containers.append(node.name)
        self.generic_visit(node)
        self.containers.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.symbols.append(
                Symbol(
                    name=alias.asname or alias.name.split(".", 1)[0],
                    kind="import",
                    path=self.rel_path,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", None),
                    module=alias.name,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * int(node.level or 0) + (node.module or "")
        for alias in node.names:
            self.symbols.append(
                Symbol(
                    name=alias.asname or alias.name,
                    kind="import",
                    path=self.rel_path,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", None),
                    module=module,
                )
            )

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        kind: SymbolKind = "method" if self.containers else "function"
        self.symbols.append(
            Symbol(
                name=node.name,
                kind=kind,
                path=self.rel_path,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", None),
                container=self._container(),
            )
        )
        self.containers.append(node.name)
        self.generic_visit(node)
        self.containers.pop()

    def _container(self) -> str | None:
        return ".".join(self.containers) if self.containers else None


def _symbols_from_javascript_like(text: str, rel_path: str) -> list[Symbol]:
    patterns: list[tuple[SymbolKind, re.Pattern[str], str | None]] = [
        ("import", re.compile(r"^\s*import\s+(?:type\s+)?(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]"), None),
        ("import", re.compile(r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*require\(['\"]([^'\"]+)['\"]\)"), "require"),
        ("class", re.compile(r"^\s*(?:export\s+default\s+|export\s+)?class\s+(\w+)"), None),
        ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+(\w+)"), None),
        ("type", re.compile(r"^\s*(?:export\s+)?type\s+(\w+)\s*="), None),
        ("enum", re.compile(r"^\s*(?:export\s+)?enum\s+(\w+)"), None),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)"), None),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"), None),
        ("const", re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*="), None),
    ]
    return _symbols_from_line_patterns(text, rel_path, patterns)


def _symbols_from_go(text: str, rel_path: str) -> list[Symbol]:
    patterns: list[tuple[SymbolKind, re.Pattern[str], str | None]] = [
        ("import", re.compile(r"^\s*import\s+(?:\w+\s+)?\"([^\"]+)\""), None),
        ("function", re.compile(r"^\s*func\s+(\w+)\s*\("), None),
        ("method", re.compile(r"^\s*func\s+\([^)]+\)\s+(\w+)\s*\("), None),
        ("struct", re.compile(r"^\s*type\s+(\w+)\s+struct\b"), None),
        ("interface", re.compile(r"^\s*type\s+(\w+)\s+interface\b"), None),
        ("type", re.compile(r"^\s*type\s+(\w+)\s+"), None),
        ("const", re.compile(r"^\s*const\s+(\w+)\b"), None),
    ]
    return _symbols_from_line_patterns(text, rel_path, patterns)


def _symbols_from_rust(text: str, rel_path: str) -> list[Symbol]:
    patterns: list[tuple[SymbolKind, re.Pattern[str], str | None]] = [
        ("import", re.compile(r"^\s*use\s+([^;]+);"), None),
        ("function", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(\w+)\s*\("), None),
        ("struct", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?struct\s+(\w+)"), None),
        ("enum", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?enum\s+(\w+)"), None),
        ("trait", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?trait\s+(\w+)"), None),
        ("type", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?type\s+(\w+)\s*="), None),
        ("const", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?const\s+(\w+)\s*:"), None),
    ]
    return _symbols_from_line_patterns(text, rel_path, patterns)


def _symbols_from_java(text: str, rel_path: str) -> list[Symbol]:
    patterns: list[tuple[SymbolKind, re.Pattern[str], str | None]] = [
        ("import", re.compile(r"^\s*import\s+(?:static\s+)?([^;]+);"), None),
        ("class", re.compile(r"^\s*(?:public|private|protected|abstract|final|\s)*class\s+(\w+)"), None),
        ("interface", re.compile(r"^\s*(?:public|private|protected|\s)*interface\s+(\w+)"), None),
        ("enum", re.compile(r"^\s*(?:public|private|protected|\s)*enum\s+(\w+)"), None),
        ("method", re.compile(r"^\s*(?:public|private|protected|static|final|synchronized|abstract|\s)+(?:[\w<>\[\], ?]+\s+)+(\w+)\s*\("), None),
    ]
    return _symbols_from_line_patterns(text, rel_path, patterns)


def _symbols_from_line_patterns(
    text: str,
    rel_path: str,
    patterns: list[tuple[SymbolKind, re.Pattern[str], str | None]],
) -> list[Symbol]:
    symbols: list[Symbol] = []
    seen: set[tuple[str, SymbolKind, int]] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "/*", "*")):
            continue
        for kind, pattern, mode in patterns:
            match = pattern.search(line)
            if not match:
                continue
            if kind == "import":
                name, module = _import_symbol_from_match(match, mode)
            else:
                name = match.group(1)
                module = None
            key = (name, kind, line_no)
            if key in seen:
                continue
            seen.add(key)
            symbols.append(
                Symbol(
                    name=name,
                    kind=kind,
                    path=rel_path,
                    line=line_no,
                    module=module,
                )
            )
            break
    return symbols


def _import_symbol_from_match(match: re.Match[str], mode: str | None) -> tuple[str, str]:
    if mode == "require":
        return match.group(1), match.group(2)
    module = match.group(1).strip()
    name = module.rsplit("/", 1)[-1].rsplit(".", 1)[-1].rsplit("::", 1)[-1].strip("{} ")
    return name or module, module
