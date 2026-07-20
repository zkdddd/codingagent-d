from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_map import ProjectMap, build_project_map, summarize_project_map
from .run_history import list_run_history


IMPROVEMENT_PRIORITIES = {
    "failed_runs": 95,
    "unverified_runs": 85,
    "missing_tests": 75,
    "long_files": 65,
    "todos": 55,
}


def suggest_self_improvements(
    root: str | Path,
    *,
    limit: int = 5,
    runs_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Suggest small, low-risk ways for the coding agent project to improve itself.

    This is intentionally read-only. It proposes candidates; it does not edit files,
    run commands, or choose a task automatically.
    """
    project_root = Path(root).resolve()
    project_map = build_project_map(project_root)
    candidates: list[dict[str, Any]] = []

    candidates.extend(_run_history_candidates(project_root, runs_dir=runs_dir))
    candidates.extend(_missing_test_candidates(project_map))
    candidates.extend(_long_file_candidates(project_root, project_map))
    candidates.extend(_todo_candidates(project_root, project_map))

    candidates.sort(
        key=lambda item: (
            -int(item.get("score") or 0),
            str(item.get("id") or ""),
        )
    )
    capped = candidates[: max(1, int(limit))]
    return {
        "ok": True,
        "workspace_root": str(project_root),
        "summary": f"Found {len(candidates)} self-improvement candidate(s)",
        "project": summarize_project_map(project_map),
        "suggestions": capped,
        "next_step": (
            "Pick one low-risk suggestion, inspect the affected files, make a small change, "
            "then run targeted validation before full validation."
        ),
    }


def _candidate(
    *,
    kind: str,
    title: str,
    rationale: str,
    files: list[str],
    action: str,
    validation: list[str],
    risk: str = "low",
    score: int | None = None,
) -> dict[str, Any]:
    safe_score = int(score if score is not None else IMPROVEMENT_PRIORITIES.get(kind, 50))
    stable_id = "-".join(
        part.strip().lower().replace(" ", "-")
        for part in [kind, files[0] if files else title]
        if part
    )
    return {
        "id": stable_id[:120],
        "kind": kind,
        "title": title,
        "rationale": rationale,
        "files": files[:8],
        "action": action,
        "validation": validation,
        "risk": risk,
        "score": safe_score,
    }


def _run_history_candidates(
    project_root: Path,
    *,
    runs_dir: str | Path | None,
) -> list[dict[str, Any]]:
    rows = list_run_history(runs_dir, limit=30)
    relevant = [
        row
        for row in rows
        if not row.get("workspace_root") or Path(str(row.get("workspace_root"))).resolve() == project_root
    ]
    failed = [
        row
        for row in relevant
        if row.get("health") in {"fail", "warn"}
        or bool(row.get("validation_failed"))
        or int(row.get("failed_tool_count") or 0) > 0
    ]
    unverified = [row for row in relevant if bool(row.get("unverified"))]
    gate_failed = [row for row in relevant if str(row.get("quality_gate_status") or "") == "fail"]
    gate_warn = [row for row in relevant if str(row.get("quality_gate_status") or "") == "warn"]

    suggestions: list[dict[str, Any]] = []
    if failed:
        changed_paths = _top_changed_paths(failed)
        suggestions.append(
            _candidate(
                kind="failed_runs",
                title="Stabilize recent failed or unhealthy Agent runs",
                rationale=(
                    f"{len(failed)} recent run(s) had failed validation, warn/fail health, "
                    "or failed tools. These are strong signals for coding reliability work."
                ),
                files=changed_paths,
                action="Inspect the newest failed run, fix the smallest repeated failure, and add or adjust a focused test.",
                validation=["python -m pytest", ".\\run-tests.bat"],
                risk="medium",
                score=IMPROVEMENT_PRIORITIES["failed_runs"] + min(len(failed), 5),
            )
        )
    if unverified:
        suggestions.append(
            _candidate(
                kind="unverified_runs",
                title="Reduce unverified code changes",
                rationale=f"{len(unverified)} recent run(s) changed files without successful validation.",
                files=_top_changed_paths(unverified),
                action="Improve validation selection so changed files trigger targeted tests before final answers.",
                validation=["python -m pytest tests", ".\\run-tests.bat"],
                risk="medium",
                score=IMPROVEMENT_PRIORITIES["unverified_runs"] + min(len(unverified), 5),
            )
        )
    if gate_failed:
        suggestions.append(
            _candidate(
                kind="failed_runs",
                title="Make quality-gate failures easier to recover from",
                rationale=(
                    f"{len(gate_failed)} recent run(s) failed the quality gate. "
                    "This means the Agent can now see failure signals, but still needs tighter recovery behavior."
                ),
                files=_top_changed_paths(gate_failed),
                action="Read the gate failure checks, then improve the narrowest recovery path that would have fixed them earlier.",
                validation=["python -m pytest tests", ".\\run-tests.bat"],
                risk="medium",
                score=IMPROVEMENT_PRIORITIES["failed_runs"] + min(len(gate_failed), 5),
            )
        )
    if gate_warn:
        suggestions.append(
            _candidate(
                kind="todos",
                title="Reduce quality-gate warning noise",
                rationale=(
                    f"{len(gate_warn)} recent run(s) only reached a warn-level quality gate. "
                    "This usually means the run is usable but the feedback loop is still too loose."
                ),
                files=_top_changed_paths(gate_warn),
                action="Pick one warning type, tighten the run workflow, and make the warning actionable in logs or prompts.",
                validation=["python -m pytest tests", ".\\run-tests.bat"],
                risk="low",
                score=IMPROVEMENT_PRIORITIES["todos"] + min(len(gate_warn), 5),
            )
        )
    return suggestions


def _missing_test_candidates(project_map: ProjectMap) -> list[dict[str, Any]]:
    unmapped = [
        path
        for path in project_map.source_files
        if path.endswith(".py") and not project_map.source_to_tests.get(path)
    ]
    if not unmapped:
        return []
    priority_files = sorted(unmapped, key=lambda path: (0 if path.startswith("kagent/agent/") else 1, path))[:8]
    return [
        _candidate(
            kind="missing_tests",
            title="Add focused tests for source files without mapped tests",
            rationale=(
                f"{len(unmapped)} Python source file(s) do not have a conventional mapped test file. "
                "Improving this makes future coding changes safer and faster to validate."
            ),
            files=priority_files,
            action="Pick one high-value source file and add a focused test file following the existing tests/test_*.py convention.",
            validation=["python -m pytest tests", ".\\run-tests.bat"],
            risk="low",
            score=IMPROVEMENT_PRIORITIES["missing_tests"] + min(len(unmapped), 10),
        )
    ]


def _long_file_candidates(project_root: Path, project_map: ProjectMap) -> list[dict[str, Any]]:
    long_files: list[tuple[str, int]] = []
    for rel_path in [*project_map.source_files, *project_map.test_files]:
        path = project_root / rel_path
        try:
            line_count = sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if line_count >= 500:
            long_files.append((rel_path, line_count))
    if not long_files:
        return []
    long_files.sort(key=lambda item: (-item[1], item[0]))
    files = [f"{path} ({line_count} lines)" for path, line_count in long_files[:5]]
    return [
        _candidate(
            kind="long_files",
            title="Split or organize the largest files",
            rationale=(
                "Large files slow down focused reading and make patches riskier. "
                f"The largest file has {long_files[0][1]} lines."
            ),
            files=files,
            action="Choose one cohesive helper or pure formatting block and extract it behind tests.",
            validation=["python -m pytest tests", ".\\run-tests.bat"],
            risk="medium",
            score=IMPROVEMENT_PRIORITIES["long_files"] + min(long_files[0][1] // 500, 10),
        )
    ]


def _todo_candidates(project_root: Path, project_map: ProjectMap) -> list[dict[str, Any]]:
    matches: list[str] = []
    for rel_path in [*project_map.source_files, *project_map.test_files]:
        path = project_root / rel_path
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                text = line.lower()
                if "todo" in text or "fixme" in text:
                    matches.append(f"{rel_path}:{line_no}")
                    break
        except OSError:
            continue
    if not matches:
        return []
    return [
        _candidate(
            kind="todos",
            title="Triage TODO/FIXME markers",
            rationale=f"{len(matches)} file(s) contain TODO/FIXME markers that may hide unfinished coding-agent behavior.",
            files=matches[:8],
            action="Review one marker, either implement the missing behavior or convert it into a documented follow-up.",
            validation=["python -m pytest tests", ".\\run-tests.bat"],
            risk="low",
            score=IMPROVEMENT_PRIORITIES["todos"] + min(len(matches), 10),
        )
    ]


def _top_changed_paths(rows: list[dict[str, Any]], limit: int = 8) -> list[str]:
    counts: dict[str, int] = {}
    for row in rows:
        for path in row.get("changed_paths") or []:
            text = str(path).strip()
            if text:
                counts[text] = counts.get(text, 0) + 1
    return [
        path
        for path, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
