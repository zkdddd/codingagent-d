from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".kagent_state",
}

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".cc", ".cpp", ".h", ".hpp"}
CONFIG_NAMES = {
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "package.json",
    "tsconfig.json",
    "pytest.ini",
    "tox.ini",
    "Cargo.toml",
    "go.mod",
    "CMakeLists.txt",
    "Makefile",
}
ENTRY_NAMES = {"main.py", "app.py", "__main__.py", "index.js", "index.ts", "main.ts", "main.js"}


@dataclass(frozen=True)
class ProjectMap:
    root: Path
    source_files: list[str]
    test_files: list[str]
    config_files: list[str]
    entry_files: list[str]
    source_to_tests: dict[str, list[str]]


def build_project_map(root: Path) -> ProjectMap:
    root = root.resolve()
    source_files: list[str] = []
    test_files: list[str] = []
    config_files: list[str] = []
    entry_files: list[str] = []

    for path in _iter_project_files(root):
        rel = path.relative_to(root).as_posix()
        if _is_test_file(path, rel):
            test_files.append(rel)
        elif path.suffix.lower() in SOURCE_SUFFIXES:
            source_files.append(rel)
        if path.name in CONFIG_NAMES:
            config_files.append(rel)
        if path.name in ENTRY_NAMES:
            entry_files.append(rel)

    source_files.sort()
    test_files.sort()
    config_files.sort()
    entry_files.sort()
    return ProjectMap(
        root=root,
        source_files=source_files,
        test_files=test_files,
        config_files=config_files,
        entry_files=entry_files,
        source_to_tests={
            source: related_tests_for_source(source, test_files)
            for source in source_files
        },
    )


def related_tests_for_source(source_path: str, test_files: list[str]) -> list[str]:
    candidates = _candidate_test_paths(source_path)
    test_set = set(test_files)
    return [candidate for candidate in candidates if candidate in test_set]


def summarize_project_map(project_map: ProjectMap) -> dict[str, object]:
    return {
        "root": str(project_map.root),
        "source_count": len(project_map.source_files),
        "test_count": len(project_map.test_files),
        "config_files": project_map.config_files[:20],
        "entry_files": project_map.entry_files[:20],
        "mapped_source_count": sum(1 for tests in project_map.source_to_tests.values() if tests),
    }


def _iter_project_files(root: Path):
    for current_raw, dirs, files in os.walk(root):
        current = Path(current_raw)
        dirs[:] = sorted(
            name
            for name in dirs
            if name not in IGNORED_DIRS and not name.startswith(".")
        )
        for name in sorted(files):
            if name.startswith("."):
                continue
            yield current / name


def _is_test_file(path: Path, rel: str) -> bool:
    parts = Path(rel).parts
    name = path.name
    return (
        bool(parts and parts[0] == "tests")
        or name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )


def _candidate_test_paths(source_path: str) -> list[str]:
    path = Path(str(source_path).replace("\\", "/"))
    if path.suffix.lower() != ".py":
        return []
    if path.parts and path.parts[0] == "tests":
        return [path.as_posix()]

    stem = path.stem
    candidates = [
        (Path("tests") / f"test_{stem}.py").as_posix(),
        (Path("tests") / f"{stem}_test.py").as_posix(),
    ]
    parts = list(path.parts)
    if parts and parts[0] in {"kagent", "src", "app"}:
        module_parts = parts[1:]
        if module_parts:
            module_stem = Path(*module_parts).with_suffix("")
            candidates.extend(
                [
                    (Path("tests") / module_stem.parent / f"test_{module_stem.name}.py").as_posix(),
                    (Path("tests") / module_stem.parent / f"{module_stem.name}_test.py").as_posix(),
                ]
            )
    return list(dict.fromkeys(candidates))
