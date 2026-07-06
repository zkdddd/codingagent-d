from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from ..config import BASE_DIR


class WorkspaceError(ValueError):
    pass


class WorkspaceTools:
    def __init__(self, root: Path | str = BASE_DIR):
        self.root = Path(root).resolve()

    def _resolve_path(self, raw_path: str) -> Path:
        if not raw_path:
            raise WorkspaceError("path is required")
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (self.root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if candidate == self.root:
            return candidate
        if self.root not in candidate.parents:
            raise WorkspaceError(f"Path outside workspace: {raw_path}")
        return candidate

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except Exception:
            return str(path)

    @staticmethod
    def _clip(text: str, limit: int = 20000) -> tuple[str, bool]:
        if limit is None or limit <= 0:
            return text, False
        if len(text) <= limit:
            return text, False
        return text[:limit], True

    def read_file(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        max_chars: int = 20000,
    ) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        if not file_path.exists():
            raise WorkspaceError(f"File not found: {self._rel(file_path)}")
        if file_path.is_dir():
            raise WorkspaceError(f"Expected a file but found a directory: {self._rel(file_path)}")

        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise WorkspaceError(f"File is not valid UTF-8 text: {self._rel(file_path)}") from exc

        lines = text.splitlines()
        total_lines = len(lines)

        if start_line is not None or end_line is not None:
            start = 1 if start_line is None else max(start_line, 1)
            stop = total_lines if end_line is None else max(end_line, 0)
            if stop and stop < start:
                raise WorkspaceError("end_line must be greater than or equal to start_line")
            selected = "\n".join(lines[start - 1:stop])
            excerpt_start = start
            excerpt_end = min(stop, total_lines)
        else:
            selected = text
            excerpt_start = 1
            excerpt_end = total_lines

        selected, truncated = self._clip(selected, max_chars)
        return {
            "path": self._rel(file_path),
            "abs_path": str(file_path),
            "start_line": excerpt_start,
            "end_line": excerpt_end,
            "line_count": total_lines,
            "content": selected,
            "truncated": truncated,
        }

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return {
            "path": self._rel(file_path),
            "abs_path": str(file_path),
            "bytes_written": len(content.encode("utf-8")),
            "line_count": len(content.splitlines()),
        }

    def run_command(
        self,
        command: str,
        cwd: str | None = None,
        timeout_ms: int = 120000,
    ) -> dict[str, Any]:
        if not command or not command.strip():
            raise WorkspaceError("command is required")

        workdir = self.root if not cwd else self._resolve_path(cwd)
        if not workdir.exists():
            raise WorkspaceError(f"Working directory not found: {self._rel(workdir)}")
        if not workdir.is_dir():
            raise WorkspaceError(f"Working directory must be a directory: {self._rel(workdir)}")

        started = time.monotonic()
        timeout_sec = max(timeout_ms, 1) / 1000.0
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
            )
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            stdout, stdout_truncated = self._clip(stdout)
            stderr, stderr_truncated = self._clip(stderr)
            return {
                "command": command,
                "cwd": self._rel(workdir),
                "returncode": None,
                "timed_out": True,
                "duration_ms": duration_ms,
                "stdout": stdout,
                "stdout_truncated": stdout_truncated,
                "stderr": stderr,
                "stderr_truncated": stderr_truncated,
            }

        duration_ms = int((time.monotonic() - started) * 1000)
        stdout, stdout_truncated = self._clip(proc.stdout or "")
        stderr, stderr_truncated = self._clip(proc.stderr or "")
        return {
            "command": command,
            "cwd": self._rel(workdir),
            "returncode": proc.returncode,
            "timed_out": timed_out,
            "duration_ms": duration_ms,
            "stdout": stdout,
            "stdout_truncated": stdout_truncated,
            "stderr": stderr,
            "stderr_truncated": stderr_truncated,
        }
