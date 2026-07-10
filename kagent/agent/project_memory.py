from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import db
from .project_map import build_project_map, summarize_project_map
from .validation_learning import learned_validation_commands_from_runs


def build_project_memory(root: str | Path) -> dict[str, Any]:
    project_root = Path(root).resolve()
    project_map = build_project_map(project_root)
    summary = summarize_project_map(project_map)
    validation_commands = _detect_validation_commands(project_root)
    project_type = _detect_project_type(project_root, summary, validation_commands)
    preferences = _stable_project_preferences(project_root)

    return {
        "workspace_root": str(project_root),
        "project_type": project_type,
        "project_summary": summary,
        "entry_files": summary.get("entry_files", []),
        "config_files": summary.get("config_files", []),
        "validation_commands": validation_commands,
        "preferences": preferences,
    }


def load_or_refresh_project_memory(root: str | Path, *, force_refresh: bool = False) -> dict[str, Any]:
    workspace_root = str(Path(root).resolve())
    if not force_refresh:
        existing = db.get_project_memory(workspace_root)
        if existing and isinstance(existing.get("memory"), dict):
            return existing["memory"]

    memory = build_project_memory(workspace_root)
    db.save_project_memory(workspace_root, memory, source="auto")
    return memory


def format_project_memory_for_prompt(memory: dict[str, Any] | None) -> str:
    if not memory:
        return ""
    summary = memory.get("project_summary") if isinstance(memory.get("project_summary"), dict) else {}
    validation_commands = memory.get("validation_commands")
    if not isinstance(validation_commands, list):
        validation_commands = []
    preferences = memory.get("preferences")
    if not isinstance(preferences, list):
        preferences = []

    lines = [
        "Long-term project memory.",
        "Use this as stable project background, but prefer current files and the latest user request.",
        f"- workspace_root: {memory.get('workspace_root') or 'unknown'}",
        f"- project_type: {memory.get('project_type') or 'unknown'}",
        f"- source_count: {summary.get('source_count', 0)}",
        f"- test_count: {summary.get('test_count', 0)}",
        f"- mapped_source_count: {summary.get('mapped_source_count', 0)}",
    ]
    entry_files = memory.get("entry_files") if isinstance(memory.get("entry_files"), list) else []
    config_files = memory.get("config_files") if isinstance(memory.get("config_files"), list) else []
    if entry_files:
        lines.append("- entry_files: " + ", ".join(str(path) for path in entry_files[:8]))
    if config_files:
        lines.append("- config_files: " + ", ".join(str(path) for path in config_files[:8]))
    if validation_commands:
        lines.append("- validation_commands:")
        for item in validation_commands[:5]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"  - {item.get('label') or 'Validation'}: `{item.get('command')}`"
                f" (cwd: {item.get('cwd') or '.'})"
            )
    if preferences:
        lines.append("- project_preferences:")
        for preference in preferences[:6]:
            lines.append(f"  - {preference}")
    return "\n".join(lines)


def _detect_validation_commands(root: Path) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    commands.extend(learned_validation_commands_from_runs())
    if (root / "run-tests.bat").exists():
        commands.append(
            {
                "label": "Full project validation",
                "command": "run-tests.bat",
                "cwd": ".",
                "reason": "Project-level test entrypoint.",
            }
        )
    if (root / "scripts" / "verify.ps1").exists():
        commands.append(
            {
                "label": "Shared verification script",
                "command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1",
                "cwd": ".",
                "reason": "Project-level verification script.",
            }
        )
    if (root / "pytest.ini").exists() or (root / "tests").exists():
        commands.append(
            {
                "label": "Pytest suite",
                "command": "python -m pytest -q",
                "cwd": ".",
                "reason": "Python tests are present.",
            }
        )
    if (root / "package.json").exists():
        commands.append(
            {
                "label": "Node package scripts",
                "command": "npm test",
                "cwd": ".",
                "reason": "package.json is present; confirm scripts before running.",
            }
        )
    return _dedupe_commands(commands)


def _detect_project_type(
    root: Path,
    summary: dict[str, object],
    validation_commands: list[dict[str, str]],
) -> str:
    config_files = {str(path).lower() for path in summary.get("config_files", []) if path}
    if {"requirements.txt", "pytest.ini", "setup.py", "pyproject.toml"} & config_files:
        return "python"
    if (root / "package.json").exists():
        return "node"
    if (root / "Cargo.toml").exists():
        return "rust"
    if (root / "go.mod").exists():
        return "go"
    if validation_commands:
        return "mixed"
    return "generic"


def _stable_project_preferences(root: Path) -> list[str]:
    preferences = [
        "Focus on code-agent capabilities before product/UI expansion.",
        "Document every feature or optimization in README and docs/agent-development.md.",
    ]
    if (root / "run-tests.bat").exists():
        preferences.append("Use run-tests.bat as the default full validation entrypoint.")
    return preferences


def _dedupe_commands(commands: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for command in commands:
        key = str(command.get("command") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(command)
    return deduped
