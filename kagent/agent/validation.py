from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .failure_diagnostics import diagnostics_summary, extract_failure_diagnostics
from .impact_analysis import related_test_commands_for_changes
from .repair_strategy import repair_strategy_prompt
from .validation_learning import learned_validation_commands_from_runs


MAX_VALIDATION_PLAN_COMMANDS = 4


def build_validation_plan(
    *,
    changed_paths: set[str],
    workspace: Any,
    max_commands: int = MAX_VALIDATION_PLAN_COMMANDS,
    symbol_impacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    project_type, project_root = _detect_validation_project(changed_paths, workspace.root)
    changed_list = sorted(str(path) for path in changed_paths if path)

    if project_type == "python":
        commands = _python_validation_commands(
            changed_paths=changed_paths,
            project_root=project_root,
            workspace=workspace,
            max_commands=max_commands,
            symbol_impacts=symbol_impacts,
        )
    elif project_type == "node":
        commands = _node_validation_commands(
            project_root=project_root or workspace.root,
            workspace=workspace,
            max_commands=max_commands,
        )
    elif project_type == "rust":
        commands = [
            {
                "label": "Cargo check",
                "reason": "Run a fast Rust compile check.",
                "command": "cargo check",
                "cwd": workspace._rel(project_root) if project_root is not None else ".",
                "timeout_ms": 240000,
            }
        ]
    elif project_type == "go":
        commands = [
            {
                "label": "Go test",
                "reason": "Run the Go package tests for the workspace.",
                "command": "go test ./...",
                "cwd": workspace._rel(project_root) if project_root is not None else ".",
                "timeout_ms": 240000,
            }
        ]
    else:
        commands = []

    if commands and project_type not in {"docs", "generic"}:
        commands = _merge_learned_validation_commands(commands, max_commands=max_commands)

    if commands:
        summary = (
            f"Detected a {project_type} project and prepared {len(commands)} validation command"
            f"{'s' if len(commands) != 1 else ''}. First step: {commands[0]['label']}."
        )
    elif project_type == "docs":
        summary = (
            "No meaningful automatic validation command was selected because the changes look like "
            "documentation or config-only edits."
        )
    else:
        summary = (
            "No safe automatic validation command was detected for this project layout. "
            "The final answer should explain that validation was not available."
        )

    return {
        "project_type": project_type,
        "summary": summary,
        "changed_paths": changed_list[:12],
        "project_root": workspace._rel(project_root) if project_root is not None else ".",
        "commands": commands,
        "command_count": len(commands),
        "selection": _validation_selection(changed_list, commands),
    }


def validation_prompt(
    changed_paths: set[str],
    plan: dict[str, Any] | None = None,
) -> str:
    files = ", ".join(sorted(changed_paths)[:8]) if changed_paths else "the changed files"
    if not isinstance(plan, dict):
        return (
            "You changed workspace files and are about to finish. "
            f"Before the final answer, run at least one validation command for {files}. "
            "Choose the most relevant lightweight check for the project and the edited files. "
            "If no meaningful validation exists, explicitly explain why."
        )

    commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
    if not commands:
        return (
            f"No safe automatic validation command was found for {files}. "
            "Explain that limitation explicitly in the final answer."
        )
    commands_text = "\n".join(_command_lines(commands))
    return (
        "You changed workspace files and are about to finish. "
        f"Before the final answer, validate {files}.\n"
        f"Detected project type: {plan.get('project_type', 'generic')}.\n"
        "Prefer these commands in order:\n"
        f"{commands_text}\n"
        "If every command is unsuitable, explicitly explain why."
    )


def validation_failure_prompt(
    *,
    changed_paths: set[str],
    summary: str | None,
    plan: dict[str, Any] | None = None,
    attempt: int = 1,
    max_attempts: int = 3,
    symbol_impacts: list[dict[str, Any]] | None = None,
) -> str:
    files = ", ".join(sorted(changed_paths)[:8]) if changed_paths else "the changed files"
    detail = f" Last validation summary: {summary}." if summary else ""
    strategy = repair_strategy_prompt(summary)
    plan_text = ""
    if isinstance(plan, dict):
        commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
        command_lines = _command_lines(commands)
        if command_lines:
            plan_text = "\nUse the validation plan again after fixing the issue:\n" + "\n".join(command_lines)
    symbol_text = ""
    symbol_lines = _symbol_failure_lines(symbol_impacts or [])
    if symbol_lines:
        symbol_text = "\nSymbol impact to consider while repairing:\n" + "\n".join(symbol_lines)
    return (
        f"The last validation failed after you changed workspace files.{detail} "
        f"This is repair attempt {attempt} of {max_attempts}. "
        f"{strategy} "
        "Inspect the failure, fix the real issue, and validate again before finishing. "
        f"Focus on {files}.{symbol_text}{plan_text}"
    )


def validation_result_summary(result: dict[str, Any], command_info: dict[str, Any]) -> str | None:
    raw_summary = str(
        result.get("summary")
        or result.get("error")
        or result.get("stderr")
        or result.get("stdout")
        or command_info.get("label")
        or ""
    ).strip()
    detail = "\n".join(
        str(result.get(key) or "")
        for key in ("stderr", "stdout", "error", "summary")
    ).lower()
    command = str(command_info.get("command") or result.get("command") or "")
    if "no module named pytest" in detail and "pytest" in command:
        hint = (
            "Pytest is not installed in the current Python environment. "
            "Install project dependencies with `python -m pip install -r requirements.txt`, "
            "then rerun `python -m pytest -q`."
        )
        return f"{raw_summary}\n{hint}" if raw_summary else hint
    diagnostic_text = diagnostics_summary(extract_failure_diagnostics(result))
    if raw_summary and diagnostic_text:
        return f"{raw_summary}\n{diagnostic_text}"
    return raw_summary or diagnostic_text


def build_focused_validation_commands(
    diagnostics: list[dict[str, Any]],
    *,
    base_command: dict[str, Any] | None = None,
    max_commands: int = 3,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    seen: set[str] = set()
    cwd = "."
    if isinstance(base_command, dict):
        cwd = str(base_command.get("cwd") or ".")

    for item in diagnostics:
        command = _focused_command_for_diagnostic(item)
        if not command or command in seen:
            continue
        seen.add(command)
        commands.append(
            {
                "label": "Focused validation",
                "reason": "Run the smallest relevant validation command for the last failure.",
                "command": command,
                "cwd": cwd,
                "timeout_ms": 180000,
                "diagnostic": item,
            }
        )
        if len(commands) >= max_commands:
            break
    return commands


def _symbol_failure_lines(symbol_impacts: list[dict[str, Any]], max_symbols: int = 5) -> list[str]:
    lines: list[str] = []
    for impact in symbol_impacts[:max_symbols]:
        if not isinstance(impact, dict):
            continue
        symbol = str(impact.get("symbol") or "").strip()
        if not symbol:
            continue
        definition = str(impact.get("definition_path") or "unknown")
        refs = impact.get("reference_count")
        tests = impact.get("related_tests") if isinstance(impact.get("related_tests"), list) else []
        line = f"- `{symbol}` at `{definition}`"
        if refs is not None:
            line += f"; references: {refs}"
        if tests:
            line += "; related tests: " + ", ".join(str(test) for test in tests[:4])
        lines.append(line)
    return lines


def _candidate_project_roots(changed_paths: set[str], workspace_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for raw_path in sorted(path for path in changed_paths if path):
        current = _normalize_changed_path(raw_path, workspace_root)
        if current.suffix:
            current = current.parent
        while True:
            if current == workspace_root or workspace_root in current.parents:
                if current not in candidates:
                    candidates.append(current)
            if current == workspace_root:
                break
            current = current.parent
    if workspace_root not in candidates:
        candidates.append(workspace_root)
    candidates.sort(key=lambda path: len(path.parts), reverse=True)
    return candidates


def _find_project_root(
    changed_paths: set[str],
    workspace_root: Path,
    markers: tuple[str, ...],
) -> Path | None:
    for candidate in _candidate_project_roots(changed_paths, workspace_root):
        if any((candidate / marker).exists() for marker in markers):
            return candidate
    return None


def _package_json_scripts(project_root: Path) -> dict[str, Any]:
    package_json = project_root / "package.json"
    if not package_json.exists():
        return {}
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def _detect_validation_project(changed_paths: set[str], workspace_root: Path) -> tuple[str, Path | None]:
    suffixes = {Path(path).suffix.lower() for path in changed_paths if path}
    node_root = _find_project_root(changed_paths, workspace_root, ("package.json",))
    if node_root is not None:
        return "node", node_root
    python_root = _find_project_root(
        changed_paths,
        workspace_root,
        ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"),
    )
    if python_root is not None or ".py" in suffixes:
        return "python", python_root
    rust_root = _find_project_root(changed_paths, workspace_root, ("Cargo.toml",))
    if rust_root is not None:
        return "rust", rust_root
    go_root = _find_project_root(changed_paths, workspace_root, ("go.mod",))
    if go_root is not None:
        return "go", go_root
    java_root = _find_project_root(changed_paths, workspace_root, ("pom.xml", "build.gradle", "build.gradle.kts"))
    if java_root is not None:
        return "java", java_root
    cpp_root = _find_project_root(changed_paths, workspace_root, ("CMakeLists.txt", "Makefile"))
    if cpp_root is not None or suffixes.intersection({".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}):
        return "cpp", cpp_root
    if suffixes and suffixes.issubset({".md", ".txt", ".rst", ".json", ".yml", ".yaml", ".toml"}):
        return "docs", None
    return "generic", None


def _python_validation_commands(
    *,
    changed_paths: set[str],
    project_root: Path | None,
    workspace: Any,
    max_commands: int,
    symbol_impacts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    command_cwd = workspace._rel(project_root) if project_root is not None else "."
    changed_py_files = sorted(
        str(_normalize_changed_path(path, workspace.root))
        for path in changed_paths
        if Path(path).suffix.lower() == ".py"
    )[:20]
    if changed_py_files:
        commands.append(
            {
                "label": "Python syntax check",
                "reason": "Compile the changed Python files to catch syntax errors quickly.",
                "command": _shell_command([sys.executable, "-m", "py_compile", *changed_py_files]),
                "cwd": command_cwd,
                "timeout_ms": 120000,
            }
        )
    else:
        compile_targets: list[str] = []
        search_root = project_root or workspace.root
        if _workspace_path_exists("main.py", base=search_root):
            compile_targets.append(str((search_root / "main.py").resolve()))
        for candidate in ("kagent", "src", "app", "tests"):
            if _workspace_path_exists(candidate, base=search_root):
                compile_targets.append(str((search_root / candidate).resolve()))
        if not compile_targets:
            compile_targets.append(str(search_root.resolve()))
        commands.append(
            {
                "label": "Python compileall",
                "reason": "Compile the Python entrypoints and packages when no direct .py file list is available.",
                "command": _shell_command([sys.executable, "-m", "compileall", *compile_targets[:6]]),
                "cwd": command_cwd,
                "timeout_ms": 120000,
            }
        )

    search_root = project_root or workspace.root
    related_commands = related_test_commands_for_changes(
        changed_paths,
        workspace_root=workspace.root,
        cwd=command_cwd,
        max_commands=max(1, max_commands - 2),
    )
    commands.extend(
        _symbol_impact_validation_commands(
            symbol_impacts or [],
            cwd=command_cwd,
            max_commands=max(1, max_commands - 2),
        )
    )
    commands.extend(related_commands)
    verify_script = _project_verify_command(search_root)
    has_pytest = (
        _workspace_path_exists("tests", base=search_root)
        or _workspace_path_exists("pytest.ini", base=search_root)
        or _workspace_path_exists("tox.ini", base=search_root)
        or "[tool.pytest" in _read_workspace_text("pyproject.toml", base=search_root).lower()
    )
    if verify_script is not None:
        commands.append(
            {
                "label": "Project verification",
                "reason": "Run the project's shared verification script after the lightweight syntax validation.",
                "command": verify_script,
                "cwd": command_cwd,
                "timeout_ms": 240000,
            }
        )
    elif has_pytest:
        commands.append(
            {
                "label": "Pytest suite",
                "reason": "Run the test suite after the lightweight syntax validation.",
                "command": _shell_command([sys.executable, "-m", "pytest", "-q"]),
                "cwd": command_cwd,
                "timeout_ms": 240000,
            }
        )
    return _select_validation_commands(commands, max_commands=max_commands)


def _node_validation_commands(
    *,
    project_root: Path,
    workspace: Any,
    max_commands: int,
) -> list[dict[str, Any]]:
    scripts = _package_json_scripts(project_root)
    if not scripts:
        return []
    command_cwd = workspace._rel(project_root)
    package_manager = "npm"
    if _workspace_path_exists("pnpm-lock.yaml", base=project_root):
        package_manager = "pnpm"
    elif _workspace_path_exists("yarn.lock", base=project_root):
        package_manager = "yarn"

    script_priority = [
        ("typecheck", "Type check", 180000),
        ("lint", "Lint", 180000),
        ("test", "Test suite", 240000),
        ("build", "Build", 240000),
    ]
    commands: list[dict[str, Any]] = []
    for script_name, label, timeout_ms in script_priority:
        if script_name not in scripts:
            continue
        commands.append(
            {
                "label": label,
                "reason": f"Run the `{script_name}` script declared in package.json.",
                "command": f"{package_manager} run {script_name}",
                "cwd": command_cwd,
                "timeout_ms": timeout_ms,
            }
        )
    return commands[:max_commands]


def _command_lines(commands: list[Any]) -> list[str]:
    command_lines = []
    for idx, command_info in enumerate(commands, start=1):
        if not isinstance(command_info, dict):
            continue
        command_lines.append(f"{idx}. {command_info.get('label')}: `{command_info.get('command')}`")
    return command_lines


def _merge_learned_validation_commands(
    commands: list[dict[str, Any]], *, max_commands: int
) -> list[dict[str, Any]]:
    learned = learned_validation_commands_from_runs(limit=max_commands)
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for command_info in [*commands, *learned]:
        if not isinstance(command_info, dict):
            continue
        command = str(command_info.get("command") or "").strip()
        if not command:
            continue
        cwd = str(command_info.get("cwd") or ".")
        key = (command, cwd)
        if key in seen:
            continue
        seen.add(key)
        merged.append(command_info)
    return _select_validation_commands(merged, max_commands=max_commands)


def _select_validation_commands(
    commands: list[dict[str, Any]], *, max_commands: int
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(command_info: dict[str, Any]) -> None:
        command = str(command_info.get("command") or "").strip()
        if not command:
            return
        key = (command, str(command_info.get("cwd") or "."))
        if key in seen or len(selected) >= max_commands:
            return
        seen.add(key)
        selected.append(command_info)

    for label in ("Python syntax check", "Python compileall"):
        for command_info in commands:
            if command_info.get("label") == label:
                add(command_info)
                break

    related_limit = max(0, max_commands - len(selected) - 1)
    for command_info in commands:
        if command_info.get("label") in {"Related tests", "Related symbol test"} and related_limit > 0:
            add(command_info)
            related_limit -= 1

    full_and_learned = [
        command_info
        for command_info in commands
        if command_info.get("label") in {"Project verification", "Pytest suite"}
        or command_info.get("learned")
        or str(command_info.get("source") or "") == "learned"
    ]
    for command_info in sorted(full_and_learned, key=_validation_command_rank, reverse=True):
        add(command_info)

    for command_info in commands:
        add(command_info)

    return selected


def _validation_command_rank(command_info: dict[str, Any]) -> tuple[float, float, float, float]:
    label = str(command_info.get("label") or "")
    learned = bool(command_info.get("learned")) or str(command_info.get("source") or "") == "learned"
    success_rate = _float_metric(command_info.get("success_rate"), default=1.0 if not learned else 0.0)
    failure_rate = _float_metric(command_info.get("failure_rate"), default=0.0)
    avg_duration = _float_metric(command_info.get("avg_duration_ms"), default=240000.0)
    coverage_bonus = 0.0
    if label == "Project verification":
        coverage_bonus = 0.18
    elif label == "Pytest suite":
        coverage_bonus = 0.14
    elif learned:
        coverage_bonus = 0.08
    speed_score = max(0.0, 1.0 - min(avg_duration, 300000.0) / 300000.0)
    learned_bonus = 0.04 if learned else 0.0
    score = (success_rate * 0.58) + ((1.0 - failure_rate) * 0.22) + (speed_score * 0.12) + coverage_bonus + learned_bonus
    return (score, success_rate, -failure_rate, -avg_duration)


def _float_metric(value: Any, *, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _validation_selection(changed_paths: list[str], commands: list[dict[str, Any]]) -> dict[str, Any]:
    tiers: list[dict[str, Any]] = []
    for command_info in commands:
        label = str(command_info.get("label") or "")
        tier = "other"
        if label in {"Python syntax check", "Python compileall"}:
            tier = "syntax"
        elif label == "Related tests":
            tier = "related_tests"
        elif label == "Related symbol test":
            tier = "symbol_related_tests"
        elif label in {"Project verification", "Pytest suite"}:
            tier = "full_validation"
        elif command_info.get("learned") or str(command_info.get("source") or "") == "learned":
            tier = "learned"
        tiers.append(
            {
                "tier": tier,
                "label": label,
                "command": command_info.get("command"),
                "reason": command_info.get("reason"),
                "success_rate": command_info.get("success_rate"),
                "failure_rate": command_info.get("failure_rate"),
                "avg_duration_ms": command_info.get("avg_duration_ms"),
                "selection_score": round(_validation_command_rank(command_info)[0], 3),
                "related_test": command_info.get("related_test"),
                "related_reason": command_info.get("related_reason"),
                "symbol": command_info.get("symbol"),
            }
        )
    return {
        "strategy": "Run fast syntax checks first, then related tests, then full project validation when available.",
        "changed_paths": changed_paths[:12],
        "tiers": tiers,
    }


def _symbol_impact_validation_commands(
    symbol_impacts: list[dict[str, Any]],
    *,
    cwd: str,
    max_commands: int,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for impact in symbol_impacts:
        if not isinstance(impact, dict):
            continue
        symbol = str(impact.get("symbol") or "").strip()
        validation_commands = (
            impact.get("validation_commands")
            if isinstance(impact.get("validation_commands"), list)
            else []
        )
        for command in validation_commands:
            command_text = str(command or "").strip()
            if not command_text:
                continue
            key = (command_text, cwd)
            if key in seen:
                continue
            seen.add(key)
            commands.append(
                {
                    "label": "Related symbol test",
                    "reason": f"Run validation suggested by symbol impact `{symbol}`.",
                    "command": command_text,
                    "cwd": cwd,
                    "timeout_ms": 180000,
                    "symbol": symbol,
                    "related_reason": f"symbol impact: {symbol}",
                }
            )
            if len(commands) >= max_commands:
                return commands
        if validation_commands:
            continue
        related_tests = impact.get("related_tests") if isinstance(impact.get("related_tests"), list) else []
        for test_path in related_tests:
            path = str(test_path or "").strip()
            if not path:
                continue
            command_text = _shell_command([sys.executable, "-m", "pytest", "-q", path])
            key = (command_text, cwd)
            if key in seen:
                continue
            seen.add(key)
            commands.append(
                {
                    "label": "Related symbol test",
                    "reason": f"Run {path} because it covers symbol impact `{symbol}`.",
                    "command": command_text,
                    "cwd": cwd,
                    "timeout_ms": 180000,
                    "related_test": path,
                    "related_reason": f"symbol impact: {symbol}",
                    "symbol": symbol,
                }
            )
            if len(commands) >= max_commands:
                return commands
    return commands


def _focused_command_for_diagnostic(item: dict[str, Any]) -> str | None:
    nodeid = item.get("nodeid")
    if nodeid:
        raw = str(nodeid).split("[", 1)[0] if "[" in str(nodeid) else str(nodeid)
        if raw.endswith(".py") or "::" in raw:
            return _shell_command([sys.executable, "-m", "pytest", "-q", str(nodeid)])

    path = item.get("path")
    if not path:
        return None
    path_text = str(path)
    if path_text.startswith("<") and path_text.endswith(">"):
        return None
    if Path(path_text).suffix.lower() != ".py":
        return None
    if path_text.replace("\\", "/").startswith("tests/"):
        return _shell_command([sys.executable, "-m", "pytest", "-q", path_text])
    return _shell_command([sys.executable, "-m", "py_compile", path_text])


def _project_verify_command(project_root: Path) -> str | None:
    verify_script = project_root / "scripts" / "verify.ps1"
    if verify_script.exists():
        return "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1"
    run_tests = project_root / "run-tests.bat"
    if run_tests.exists():
        return "run-tests.bat"
    return None


def _shell_command(parts: list[str]) -> str:
    return subprocess.list2cmdline(parts)


def _workspace_path_exists(relative_path: str, base: Path) -> bool:
    return (base / relative_path).exists()


def _read_workspace_text(relative_path: str, *, base: Path, limit: int = 20000) -> str:
    path = base / relative_path
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except Exception:
        return ""


def _normalize_changed_path(raw_path: str, workspace_root: Path) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (workspace_root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate
