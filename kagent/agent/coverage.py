from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import STATE_DIR

# A coverage drop beyond this fraction of lines is flagged as a regression.
_COVERAGE_REGRESSION_THRESHOLD = 0.03
_COVERAGE_HISTORY_LIMIT = 50


def measure_coverage(
    root: str | Path,
    *,
    pytest_args: list[str] | None = None,
    timeout: int = 600,
) -> dict[str, Any] | None:
    """Run pytest under coverage and return {line_rate, branch_rate, ...}.

    Returns None when the project has no tests or coverage cannot be collected,
    so callers can treat "no coverage signal" gracefully instead of crashing.
    """
    root_path = Path(root)
    data_file = root_path / ".kagent" / ".coverage"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    args = list(pytest_args or ["-q"])

    run_cmd = [
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--source=.",
        f"--data-file={data_file}",
        "-m",
        "pytest",
        *args,
    ]
    try:
        subprocess.run(
            run_cmd,
            cwd=str(root_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        _cleanup(data_file)
        return None

    if not data_file.exists():
        return None

    json_file = root_path / ".kagent" / "coverage-report.json"
    json_cmd = [
        sys.executable,
        "-m",
        "coverage",
        "json",
        f"--data-file={data_file}",
        "-o",
        str(json_file),
    ]
    try:
        subprocess.run(
            json_cmd,
            cwd=str(root_path),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if not json_file.exists():
            return None
        report = json.loads(json_file.read_text(encoding="utf-8"))
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        return None
    finally:
        _cleanup(data_file)
        _cleanup(json_file)

    totals = report.get("totals") if isinstance(report, dict) else None
    if not isinstance(totals, dict):
        return None
    line_rate = _to_rate(totals.get("percent_covered"))
    if line_rate is None:
        return None
    return {
        "line_rate": round(line_rate, 4),
        "branch_rate": _to_rate(totals.get("percent_covered_branches")),
        "covered_lines": int(totals.get("covered_lines") or 0),
        "num_statements": int(totals.get("num_statements") or 0),
        "missing_lines": int(totals.get("missing_lines") or 0),
    }


def save_coverage_snapshot(root: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    """Append a coverage snapshot to the persistent history."""
    history = _read_history(root)
    history.append({"line_rate": result.get("line_rate"), **result})
    history = history[-_COVERAGE_HISTORY_LIMIT:]
    _write_history(root, history)
    return _trend_from_history(history)


def coverage_trend(root: str | Path) -> dict[str, Any]:
    """Return the coverage trend from persisted history (recent vs baseline)."""
    return _trend_from_history(_read_history(root))


def coverage_regression_gate(trend: dict[str, Any]) -> dict[str, Any]:
    """Decide pass/warn from a coverage trend. Warns on a sustained drop."""
    status = "pass"
    message = "coverage stable or improving"
    recent = trend.get("recent_line_rate")
    baseline = trend.get("baseline_line_rate")
    delta = trend.get("delta")
    if recent is None or baseline is None or delta is None:
        status = "pass"
        message = "insufficient coverage history"
    elif delta <= -_COVERAGE_REGRESSION_THRESHOLD:
        status = "warn"
        message = (
            f"coverage dropped {abs(round(delta * 100, 1))}% "
            f"({round(baseline * 100, 1)}% -> {round(recent * 100, 1)}%)"
        )
    return {
        "status": status,
        "message": message,
        "recent_line_rate": recent,
        "baseline_line_rate": baseline,
        "delta": delta,
    }


def _trend_from_history(history: list[dict[str, Any]]) -> dict[str, Any]:
    rates = [
        float(item.get("line_rate") or 0)
        for item in history
        if isinstance(item, dict) and item.get("line_rate") is not None
    ]
    if not rates:
        return {
            "samples": 0,
            "recent_line_rate": None,
            "baseline_line_rate": None,
            "delta": None,
        }
    recent = rates[-1]
    baseline = sum(rates) / len(rates) if rates else recent
    delta = recent - baseline
    return {
        "samples": len(rates),
        "recent_line_rate": round(recent, 4),
        "baseline_line_rate": round(baseline, 4),
        "delta": round(delta, 4),
    }


def _history_path(root: str | Path) -> Path:
    return Path(STATE_DIR) / "coverage_history.json"


def _read_history(root: str | Path) -> list[dict[str, Any]]:
    path = _history_path(root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _write_history(root: str | Path, history: list[dict[str, Any]]) -> None:
    path = _history_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")


def _cleanup(data_file: Path) -> None:
    try:
        data_file.unlink(missing_ok=True)
    except OSError:
        pass


def _to_rate(value: Any) -> float | None:
    if value is None:
        return None
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    # coverage reports percent_covered in 0-100; normalize to 0-1.
    return rate / 100.0 if rate > 1.5 else rate
