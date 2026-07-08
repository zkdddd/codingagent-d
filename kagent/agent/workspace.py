from __future__ import annotations

import difflib
import fnmatch
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .. import db
from ..config import (
    ALLOWED_COMMAND_ROOTS,
    ALLOWED_WRITE_ROOTS,
    FILESYSTEM_COMMAND_SCOPE,
    FILESYSTEM_READ_SCOPE,
    FILESYSTEM_WRITE_SCOPE,
    ROLLBACK_ROOT,
    WORKSPACE_ROOT,
)


DEFAULT_IGNORED_DIRS = {
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
}


class WorkspaceError(ValueError):
    pass


class WorkspaceTools:
    def __init__(self, root: Path | str = WORKSPACE_ROOT, session_id: str | None = None):
        self.root = Path(root).resolve()
        self.session_id = session_id
        self.rollback_root = Path(ROLLBACK_ROOT).resolve()
        self.read_scope = self._normalize_scope(FILESYSTEM_READ_SCOPE, default="all")
        self.write_scope = self._normalize_scope(FILESYSTEM_WRITE_SCOPE, default="workspace")
        self.command_scope = self._normalize_scope(
            FILESYSTEM_COMMAND_SCOPE,
            default="workspace",
        )
        self.allowed_write_roots = self._parse_roots(ALLOWED_WRITE_ROOTS)
        self.allowed_command_roots = self._parse_roots(ALLOWED_COMMAND_ROOTS)

    @staticmethod
    def _normalize_scope(raw: str, default: str) -> str:
        value = str(raw or default).strip().lower()
        return value if value in {"workspace", "all"} else default

    @staticmethod
    def _parse_roots(raw: str) -> list[Path]:
        roots: list[Path] = []
        for item in str(raw or "").split(os.pathsep):
            item = item.strip().strip('"')
            if item:
                roots.append(Path(item).expanduser().resolve())
        return roots

    @staticmethod
    def _path_is_within(path: Path, root: Path) -> bool:
        return path == root or root in path.parents

    def _allowed_roots_for_access(self, access: str) -> list[Path]:
        if access == "write":
            return [self.root, *self.allowed_write_roots]
        if access == "command":
            return [self.root, *self.allowed_command_roots]
        return [self.root]

    def _scope_for_access(self, access: str) -> str:
        if access == "write":
            return self.write_scope
        if access == "command":
            return self.command_scope
        return self.read_scope

    def _resolve_path(self, raw_path: str, access: str = "read") -> Path:
        if not raw_path:
            raise WorkspaceError("path is required")
        access = access if access in {"read", "write", "command"} else "read"
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (self.root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if self._scope_for_access(access) == "all":
            return candidate
        if not any(
            self._path_is_within(candidate, root)
            for root in self._allowed_roots_for_access(access)
        ):
            raise WorkspaceError(
                f"Path outside allowed {access} roots: {raw_path}"
            )
        return candidate

    def _rel(self, path: Path) -> str:
        try:
            rel = path.relative_to(self.root)
            return "." if not rel.parts else rel.as_posix()
        except Exception:
            return path.as_posix() if isinstance(path, Path) else str(path)

    def _snapshot_rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            absolute = path.resolve()
            drive = absolute.drive.rstrip(":").replace("\\", "_").replace("/", "_")
            parts = [part for part in absolute.parts if part not in {absolute.anchor, absolute.drive}]
            safe_parts = [self._safe_token(part) for part in parts]
            prefix = self._safe_token(drive or "root")
            return str(Path("__absolute__") / prefix / Path(*safe_parts))

    @staticmethod
    def _safe_token(raw: str) -> str:
        cleaned = "".join(
            ch if ch.isalnum() or ch in {"-", "_", "."} else "_"
            for ch in raw.strip()
        )
        return cleaned or "default"

    def _rollback_session_root(self) -> Path:
        target = self.rollback_root / self._safe_token(self.session_id or "default")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _snapshot_root_for_token(self, token: str) -> Path:
        return self._rollback_session_root() / token

    @staticmethod
    def _new_rollback_token() -> str:
        return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:10]

    def _cleanup_snapshot_token(self, token: str | None) -> None:
        if not token:
            return
        snapshot_root = self._snapshot_root_for_token(token)
        if snapshot_root.exists():
            shutil.rmtree(snapshot_root, ignore_errors=True)

    def _remove_path_if_exists(self, path: Path) -> None:
        if not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path)
            return
        path.unlink()

    def _capture_path_state(self, path: Path, snapshot_root: Path) -> dict[str, Any]:
        rel_path = self._rel(path)
        if not path.exists():
            return {"path": rel_path, "kind": "missing"}

        snapshot_rel = self._snapshot_rel(path)
        snapshot_path = snapshot_root / Path(snapshot_rel)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, snapshot_path)
            kind = "dir"
        else:
            shutil.copy2(path, snapshot_path)
            kind = "file"
        return {
            "path": rel_path,
            "kind": kind,
            "snapshot_rel": snapshot_rel,
        }

    def _capture_restore_states(
        self,
        paths: list[Path],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        if not self.session_id:
            return None, []

        unique_paths: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            unique_paths.append(path)

        snapshot_token = self._new_rollback_token()
        snapshot_root = self._snapshot_root_for_token(snapshot_token)
        states = [self._capture_path_state(path, snapshot_root) for path in unique_paths]
        return snapshot_token, states

    def _save_restore_rollback(
        self,
        tool_name: str,
        summary: str,
        snapshot_token: str | None,
        states: list[dict[str, Any]],
    ) -> int | None:
        if not self.session_id:
            return None
        payload: dict[str, Any] = {
            "action": "restore_states",
            "states": states,
        }
        if snapshot_token:
            payload["snapshot_token"] = snapshot_token
        try:
            return db.save_rollback_entry(
                self.session_id,
                tool_name,
                summary,
                payload,
            )
        except Exception:
            self._cleanup_snapshot_token(snapshot_token)
            raise

    def _restore_path_state(
        self,
        state: dict[str, Any],
        snapshot_root: Path | None,
    ) -> str:
        target = self._resolve_path(str(state["path"]), access="write")
        kind = str(state.get("kind") or "")

        if kind == "missing":
            self._remove_path_if_exists(target)
            return self._rel(target)

        snapshot_rel = str(state.get("snapshot_rel") or "")
        if not snapshot_root or not snapshot_rel:
            raise WorkspaceError(f"Rollback snapshot missing for {self._rel(target)}")

        snapshot_path = snapshot_root / Path(snapshot_rel)
        if not snapshot_path.exists():
            raise WorkspaceError(f"Rollback snapshot not found for {self._rel(target)}")

        self._remove_path_if_exists(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind == "dir":
            shutil.copytree(snapshot_path, target)
        elif kind == "file":
            shutil.copy2(snapshot_path, target)
        else:
            raise WorkspaceError(f"Unsupported rollback state: {kind}")
        return self._rel(target)

    @staticmethod
    def _clip(text: str, limit: int = 20000) -> tuple[str, bool]:
        if limit is None or limit <= 0:
            return text, False
        if len(text) <= limit:
            return text, False
        return text[:limit], True

    @staticmethod
    def _is_hidden(name: str) -> bool:
        return name.startswith(".")

    @staticmethod
    def _is_text_file(path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".pdf", ".zip", ".7z", ".tar", ".gz", ".bz2", ".xz", ".pyc", ".pyd", ".dll", ".exe", ".so", ".dylib"}:
            return False
        return True

    def _iter_directory(
        self,
        root: Path,
        max_depth: int | None,
        ignore_hidden: bool,
    ):
        start_depth = len(root.parts)
        for current_root, dirs, files in os.walk(root):
            current = Path(current_root)
            depth = len(current.parts) - start_depth
            if max_depth is not None and depth > max_depth:
                dirs[:] = []
                continue

            dirs.sort()
            files.sort()

            if ignore_hidden:
                dirs[:] = [
                    d
                    for d in dirs
                    if not self._is_hidden(d) and d not in DEFAULT_IGNORED_DIRS
                ]
                files = [f for f in files if not self._is_hidden(f)]

            yield current, depth, dirs, files

    def _patch_paths(self, patch_text: str) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()
        for line in patch_text.splitlines():
            if line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    candidate = parts[3]
                    if candidate.startswith("b/"):
                        rel = candidate[2:]
                        if rel not in seen:
                            seen.add(rel)
                            paths.append(rel)
            elif line.startswith("+++ b/"):
                rel = line[6:].strip()
                if rel != "/dev/null" and rel not in seen:
                    seen.add(rel)
                    paths.append(rel)
        return paths

    def _closest_path_matches(self, missing_path: Path, max_suggestions: int = 3) -> list[str]:
        anchor = missing_path.parent
        while True:
            if anchor.exists() and anchor.is_dir():
                break
            if anchor == self.root or anchor.parent == anchor:
                if not anchor.exists() or not anchor.is_dir():
                    return []
                break
            anchor = anchor.parent

        try:
            names = sorted({child.name for child in anchor.iterdir()})
        except OSError:
            return []

        matches = difflib.get_close_matches(
            missing_path.name,
            names,
            n=max_suggestions,
            cutoff=0.45,
        )
        return [self._rel(anchor / name) for name in matches]

    def _not_found_message(self, label: str, missing_path: Path) -> str:
        message = f"{label} not found: {self._rel(missing_path)}"
        suggestions = self._closest_path_matches(missing_path)
        if suggestions:
            message += ". Did you mean: " + ", ".join(suggestions)
        return message

    @staticmethod
    def _first_nonempty_line(text: str) -> str | None:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        return None

    def _count_tree_items(self, path: Path, limit: int = 2000) -> tuple[int, bool]:
        if path.is_file():
            return 1, False

        count = 0
        for _, dirs, files in os.walk(path):
            count += len(dirs) + len(files)
            if count >= limit:
                return count, True
        return count, False

    @classmethod
    def _command_summary(
        cls,
        returncode: int | None,
        timed_out: bool,
        duration_ms: int,
        stdout: str,
        stderr: str,
    ) -> str:
        if timed_out:
            detail = cls._first_nonempty_line(stderr) or cls._first_nonempty_line(stdout)
            if detail:
                return f"Timed out after {duration_ms} ms: {detail}"
            return f"Timed out after {duration_ms} ms"

        if returncode == 0:
            detail = cls._first_nonempty_line(stdout) or cls._first_nonempty_line(stderr)
            if detail:
                return f"OK: {detail}"
            return f"Completed with exit 0 in {duration_ms} ms"

        detail = cls._first_nonempty_line(stderr) or cls._first_nonempty_line(stdout)
        if detail:
            return f"Exit {returncode}: {detail}"
        return f"Failed with exit {returncode} in {duration_ms} ms"

    def read_file(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        max_chars: int = 20000,
    ) -> dict[str, Any]:
        file_path = self._resolve_path(path, access="read")
        if not file_path.exists():
            raise WorkspaceError(self._not_found_message("File", file_path))
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

    def list_files(
        self,
        path: str = ".",
        max_depth: int | None = 3,
        include_dirs: bool = True,
        include_hidden: bool = False,
        max_results: int = 500,
    ) -> dict[str, Any]:
        start = self._resolve_path(path, access="read")
        if not start.exists():
            raise WorkspaceError(self._not_found_message("Path", start))
        if start.is_file():
            start = start.parent
        if not start.is_dir():
            raise WorkspaceError(f"Expected a directory but found a file: {self._rel(start)}")

        if max_depth is not None:
            max_depth = max(0, int(max_depth))
        max_results = max(1, int(max_results))

        items: list[dict[str, Any]] = []
        truncated = False
        ignored_count = 0

        for current, depth, dirs, files in self._iter_directory(start, max_depth, not include_hidden):
            if include_dirs:
                for name in dirs:
                    if not include_hidden and name in DEFAULT_IGNORED_DIRS:
                        ignored_count += 1
                        continue
                    child = current / name
                    rel = self._rel(child)
                    if len(items) >= max_results:
                        truncated = True
                        break
                    items.append(
                        {
                            "type": "dir",
                            "name": name,
                            "path": rel,
                            "depth": depth + 1,
                        }
                    )
                if truncated:
                    break

            for name in files:
                child = current / name
                rel = self._rel(child)
                if len(items) >= max_results:
                    truncated = True
                    break
                stat = child.stat()
                items.append(
                    {
                        "type": "file",
                        "name": name,
                        "path": rel,
                        "depth": depth + 1,
                        "size": stat.st_size,
                    }
                )
            if truncated:
                break

        return {
            "root": str(start),
            "path": self._rel(start),
            "items": items,
            "count": len(items),
            "truncated": truncated,
            "ignored_count": ignored_count,
            "max_depth": max_depth,
        }

    def search_file(
        self,
        query: str,
        path: str = ".",
        file_glob: str = "*",
        case_sensitive: bool = False,
        include_hidden: bool = False,
        context_lines: int = 1,
        max_results: int = 50,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            raise WorkspaceError("query is required")

        start = self._resolve_path(path, access="read")
        if not start.exists():
            raise WorkspaceError(self._not_found_message("Path", start))

        if start.is_file():
            candidates = [start]
            base_dir = start.parent
        else:
            base_dir = start
            candidates = []
            for current, _, dirs, files in self._iter_directory(start, None, not include_hidden):
                for name in files:
                    child = current / name
                    rel = child.relative_to(base_dir).as_posix()
                    if fnmatch.fnmatch(name, file_glob) or fnmatch.fnmatch(rel, file_glob):
                        candidates.append(child)

        max_results = max(1, int(max_results))
        context_lines = max(0, int(context_lines))
        needle = query if case_sensitive else query.lower()

        matches: list[dict[str, Any]] = []
        scanned = 0
        skipped_binary = 0
        truncated = False

        for file_path in candidates:
            if len(matches) >= max_results:
                truncated = True
                break
            if file_path.is_dir():
                continue
            scanned += 1
            if file_path.stat().st_size > 1_500_000:
                continue
            if not self._is_text_file(file_path):
                skipped_binary += 1
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                skipped_binary += 1
                continue

            lines = text.splitlines()
            for line_no, line in enumerate(lines, start=1):
                haystack = line if case_sensitive else line.lower()
                if needle not in haystack:
                    continue

                start_line = max(1, line_no - context_lines)
                end_line = min(len(lines), line_no + context_lines)
                snippet = "\n".join(lines[start_line - 1 : end_line])
                matches.append(
                    {
                        "path": self._rel(file_path),
                        "line_number": line_no,
                        "line": line,
                        "snippet": snippet,
                        "start_line": start_line,
                        "end_line": end_line,
                    }
                )
                if len(matches) >= max_results:
                    truncated = True
                    break
            if truncated:
                break

        return {
            "query": query,
            "path": self._rel(start),
            "file_glob": file_glob,
            "matches": matches,
            "count": len(matches),
            "scanned_files": scanned,
            "skipped_binary": skipped_binary,
            "truncated": truncated,
            "case_sensitive": case_sensitive,
            "context_lines": context_lines,
        }

    def apply_patch(self, patch: str) -> dict[str, Any]:
        if not patch or not patch.strip():
            raise WorkspaceError("patch is required")

        files_touched = self._patch_paths(patch)
        snapshot_token, restore_states = self._capture_restore_states(
            [self._resolve_path(path, access="write") for path in files_touched]
        )
        proc = subprocess.run(
            ["git", "apply", "--recount", "--whitespace=nowarn"],
            cwd=str(self.root),
            input=patch.encode("utf-8"),
            capture_output=True,
        )
        stderr = (proc.stderr or b"").decode("utf-8", "replace").strip()
        stdout = (proc.stdout or b"").decode("utf-8", "replace").strip()
        skipped = "skipped patch" in stderr.lower() or "skipped patch" in stdout.lower()
        if proc.returncode != 0 or skipped:
            self._cleanup_snapshot_token(snapshot_token)
            message = stderr or stdout or "git apply failed"
            if skipped and "skipped patch" not in message.lower():
                message = f"{message}\nSkipped patch."
            raise WorkspaceError(message)

        summary = (
            f"Applied patch to {len(files_touched)} file{'s' if len(files_touched) != 1 else ''}"
        )
        rollback_id = self._save_restore_rollback(
            "apply_patch",
            summary,
            snapshot_token,
            restore_states,
        )
        return {
            "ok": True,
            "files_touched": files_touched,
            "file_count": len(files_touched),
            "patch_bytes": len(patch.encode("utf-8")),
            "rollback_id": rollback_id,
            "summary": summary,
        }

    def preview_patch(self, patch: str) -> dict[str, Any]:
        if not patch or not patch.strip():
            raise WorkspaceError("patch is required")

        files_touched = self._patch_paths(patch)
        return {
            "files_touched": files_touched,
            "file_count": len(files_touched),
            "patch_bytes": len(patch.encode("utf-8")),
            "patch_lines": patch.count("\n") + 1,
        }

    def preview_write_file(self, path: str, content: str, max_preview_chars: int = 8000) -> dict[str, Any]:
        file_path = self._resolve_path(path, access="write")
        if file_path.exists() and file_path.is_dir():
            raise WorkspaceError(f"Expected a file but found a directory: {self._rel(file_path)}")

        existed = file_path.exists()
        before = ""
        if existed:
            try:
                before = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise WorkspaceError(f"File is not valid UTF-8 text: {self._rel(file_path)}") from exc

        rel_path = self._rel(file_path)
        diff_lines = list(
            difflib.unified_diff(
                before.splitlines(),
                content.splitlines(),
                fromfile=rel_path if existed else "/dev/null",
                tofile=rel_path,
                lineterm="",
            )
        )
        preview = "\n".join(diff_lines) or "(no content changes)"
        preview, preview_truncated = self._clip(preview, max_preview_chars)
        return {
            "path": rel_path,
            "abs_path": str(file_path),
            "exists": existed,
            "bytes_written": len(content.encode("utf-8")),
            "line_count": len(content.splitlines()),
            "preview": preview,
            "preview_truncated": preview_truncated,
        }

    def preview_command(
        self,
        command: str,
        cwd: str | None = None,
        timeout_ms: int = 120000,
    ) -> dict[str, Any]:
        if not command or not command.strip():
            raise WorkspaceError("command is required")

        workdir = self.root if not cwd else self._resolve_path(cwd, access="command")
        if not workdir.exists():
            raise WorkspaceError(self._not_found_message("Working directory", workdir))
        if not workdir.is_dir():
            raise WorkspaceError(f"Working directory must be a directory: {self._rel(workdir)}")

        cwd_rel = self._rel(workdir)
        preview = f"$ {command}\n# cwd: {cwd_rel}\n# timeout_ms: {int(timeout_ms)}"
        return {
            "command": command,
            "cwd": cwd_rel,
            "timeout_ms": int(timeout_ms),
            "preview": preview,
        }

    def preview_rename_path(self, source_path: str, target_path: str) -> dict[str, Any]:
        source = self._resolve_path(source_path, access="write")
        target = self._resolve_path(target_path, access="write")

        if not source.exists():
            raise WorkspaceError(self._not_found_message("Path", source))
        if source == target:
            raise WorkspaceError("source_path and target_path must be different")
        if target.exists():
            raise WorkspaceError(f"Target already exists: {self._rel(target)}")
        if not target.parent.exists():
            raise WorkspaceError(self._not_found_message("Target parent directory", target.parent))

        item_type = "directory" if source.is_dir() else "file"
        preview = f"rename {item_type}: {self._rel(source)} -> {self._rel(target)}"
        return {
            "source_path": self._rel(source),
            "target_path": self._rel(target),
            "item_type": item_type,
            "preview": preview,
        }

    def preview_copy_path(self, source_path: str, target_path: str) -> dict[str, Any]:
        source = self._resolve_path(source_path, access="read")
        target = self._resolve_path(target_path, access="write")

        if not source.exists():
            raise WorkspaceError(self._not_found_message("Path", source))
        if source == target:
            raise WorkspaceError("source_path and target_path must be different")
        if target.exists():
            raise WorkspaceError(f"Target already exists: {self._rel(target)}")
        if not target.parent.exists():
            raise WorkspaceError(self._not_found_message("Target parent directory", target.parent))

        item_type = "directory" if source.is_dir() else "file"
        item_count, truncated = self._count_tree_items(source)
        suffix = " (count truncated)" if truncated else ""
        preview = (
            f"copy {item_type}: {self._rel(source)} -> {self._rel(target)}"
            f"\n# items: {item_count}{suffix}"
        )
        return {
            "source_path": self._rel(source),
            "target_path": self._rel(target),
            "item_type": item_type,
            "item_count": item_count,
            "item_count_truncated": truncated,
            "preview": preview,
        }

    def preview_delete_path(self, path: str, recursive: bool = True) -> dict[str, Any]:
        target = self._resolve_path(path, access="write")
        if target == self.root or target.parent == target:
            raise WorkspaceError("Refusing to delete a workspace or filesystem root")
        if not target.exists():
            raise WorkspaceError(self._not_found_message("Path", target))

        item_type = "directory" if target.is_dir() else "file"
        item_count, truncated = self._count_tree_items(target)
        if target.is_dir() and any(target.iterdir()) and not recursive:
            raise WorkspaceError(
                f"Directory is not empty: {self._rel(target)}. Set recursive=true to delete it."
            )

        suffix = " (count truncated)" if truncated else ""
        preview = (
            f"delete {item_type}: {self._rel(target)}"
            f"\n# recursive: {bool(recursive)}"
            f"\n# items: {item_count}{suffix}"
        )
        return {
            "path": self._rel(target),
            "item_type": item_type,
            "recursive": bool(recursive),
            "item_count": item_count,
            "item_count_truncated": truncated,
            "preview": preview,
        }

    def preview_make_directory(self, path: str) -> dict[str, Any]:
        target = self._resolve_path(path, access="write")
        if target.exists() and not target.is_dir():
            raise WorkspaceError(f"Expected a directory path but found a file: {self._rel(target)}")
        if not target.parent.exists():
            raise WorkspaceError(self._not_found_message("Target parent directory", target.parent))

        exists = target.exists()
        preview = (
            f"create directory: {self._rel(target)}"
            if not exists
            else f"directory already exists: {self._rel(target)}"
        )
        return {
            "path": self._rel(target),
            "exists": exists,
            "preview": preview,
        }

    def _state_for_diff(self, path: Path | None) -> dict[str, Any]:
        if path is None or not path.exists():
            return {"kind": "missing"}
        if path.is_dir():
            return {"kind": "dir"}
        if not self._is_text_file(path):
            return {"kind": "binary"}
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"kind": "binary"}
        return {"kind": "file", "text": text}

    def _rollback_diff_section(
        self,
        rel_path: str,
        current_path: Path,
        snapshot_path: Path | None,
    ) -> dict[str, Any]:
        current_state = self._state_for_diff(current_path)
        snapshot_state = self._state_for_diff(snapshot_path)
        current_kind = str(current_state.get("kind") or "missing")
        snapshot_kind = str(snapshot_state.get("kind") or "missing")

        if current_kind == "file" and snapshot_kind == "file":
            diff_lines = list(
                difflib.unified_diff(
                    str(current_state.get("text", "")).splitlines(),
                    str(snapshot_state.get("text", "")).splitlines(),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                    lineterm="",
                )
            )
            preview = "\n".join(diff_lines) or f"# no text changes for {rel_path}"
            return {
                "path": rel_path,
                "action": "update",
                "diff_available": True,
                "preview": preview,
            }

        if current_kind == "missing" and snapshot_kind == "file":
            diff_lines = list(
                difflib.unified_diff(
                    [],
                    str(snapshot_state.get("text", "")).splitlines(),
                    fromfile="/dev/null",
                    tofile=f"b/{rel_path}",
                    lineterm="",
                )
            )
            preview = "\n".join(diff_lines) or f"# restore file {rel_path}"
            return {
                "path": rel_path,
                "action": "restore_file",
                "diff_available": True,
                "preview": preview,
            }

        if current_kind == "file" and snapshot_kind == "missing":
            diff_lines = list(
                difflib.unified_diff(
                    str(current_state.get("text", "")).splitlines(),
                    [],
                    fromfile=f"a/{rel_path}",
                    tofile="/dev/null",
                    lineterm="",
                )
            )
            preview = "\n".join(diff_lines) or f"# delete file {rel_path}"
            return {
                "path": rel_path,
                "action": "delete_file",
                "diff_available": True,
                "preview": preview,
            }

        note = (
            f"# {rel_path}\n"
            f"# current: {current_kind}\n"
            f"# target: {snapshot_kind}\n"
            "# text diff unavailable for this item"
        )
        action = "replace_item"
        if current_kind == "missing" and snapshot_kind == "dir":
            action = "restore_directory"
        elif current_kind == "dir" and snapshot_kind == "missing":
            action = "delete_directory"
        elif current_kind == "dir" and snapshot_kind == "dir":
            action = "restore_directory"
        elif current_kind == "binary" or snapshot_kind == "binary":
            action = "replace_binary"
        return {
            "path": rel_path,
            "action": action,
            "diff_available": False,
            "preview": note,
        }

    def _rollback_preview_payload(
        self,
        entry: dict[str, Any],
        superseded_active_count: int = 0,
        max_preview_chars: int = 12000,
    ) -> dict[str, Any]:
        paths = self._rollback_entry_paths(entry)
        status = str(entry.get("status") or "")
        available = status == "active"
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        snapshot_token = payload.get("snapshot_token")
        snapshot_root = (
            self._snapshot_root_for_token(str(snapshot_token))
            if snapshot_token
            else None
        )

        diff_entries: list[dict[str, Any]] = []
        preview_sections: list[str] = [
            f"# rollback #{entry['id']} from {entry['tool_name']}",
            f"# status: {status}",
            f"# created_at: {entry['created_at']}",
            f"# summary: {entry['summary']}",
        ]
        if superseded_active_count > 0:
            preview_sections.append(
                f"# warning: this will supersede {superseded_active_count} newer active rollback entr"
                + ("ies" if superseded_active_count != 1 else "y")
            )

        states = payload.get("states") if isinstance(payload.get("states"), list) else []
        for state in states:
            if not isinstance(state, dict):
                continue
            rel_path = str(state.get("path") or "")
            if not rel_path:
                continue
            snapshot_rel = str(state.get("snapshot_rel") or "")
            snapshot_path = (
                snapshot_root / Path(snapshot_rel)
                if snapshot_root is not None and snapshot_rel
                else None
            )
            section = self._rollback_diff_section(
                rel_path=rel_path,
                current_path=self._resolve_path(rel_path, access="read"),
                snapshot_path=snapshot_path,
            )
            diff_entries.append(
                {
                    "path": section["path"],
                    "action": section["action"],
                    "diff_available": section["diff_available"],
                }
            )
            preview_sections.append("")
            preview_sections.append(section["preview"])

        preview, preview_truncated = self._clip(
            "\n".join(preview_sections).strip(),
            max_preview_chars,
        )
        return {
            "rollback_id": int(entry["id"]),
            "source_tool": str(entry["tool_name"]),
            "summary": str(entry["summary"]),
            "created_at": str(entry["created_at"]),
            "status": status,
            "paths": paths,
            "path_count": len(paths),
            "superseded_active_count": superseded_active_count,
            "available": available,
            "diff_entries": diff_entries,
            "preview": preview,
            "preview_truncated": preview_truncated,
        }

    @staticmethod
    def _rollback_preview_unavailable(summary: str, preview: str) -> dict[str, Any]:
        return {
            "rollback_id": None,
            "source_tool": "",
            "summary": summary,
            "created_at": "",
            "status": "",
            "paths": [],
            "path_count": 0,
            "superseded_active_count": 0,
            "available": False,
            "diff_entries": [],
            "preview_truncated": False,
            "preview": preview,
        }

    @staticmethod
    def _rollback_entry_paths(entry: dict[str, Any]) -> list[str]:
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        states = payload.get("states") if isinstance(payload.get("states"), list) else []
        return [
            str(state.get("path"))
            for state in states
            if isinstance(state, dict) and state.get("path")
        ]

    def _preview_rollback_entry(
        self,
        entry: dict[str, Any],
        superseded_active_count: int = 0,
    ) -> dict[str, Any]:
        return self._rollback_preview_payload(
            entry,
            superseded_active_count=superseded_active_count,
            max_preview_chars=12000,
        )

    def list_rollback_history(
        self,
        limit: int = 12,
        include_inactive: bool = True,
    ) -> dict[str, Any]:
        if not self.session_id:
            return {
                "entries": [],
                "count": 0,
                "include_inactive": bool(include_inactive),
                "summary": "Rollback history is unavailable without an active chat session",
                "preview": "rollback history unavailable without an active chat session",
            }

        entries = db.list_rollback_entries(
            self.session_id,
            limit=max(1, int(limit)),
            include_inactive=bool(include_inactive),
        )
        items: list[dict[str, Any]] = []
        preview_lines: list[str] = []
        for entry in entries:
            paths = self._rollback_entry_paths(entry)
            item = {
                "rollback_id": int(entry["id"]),
                "source_tool": str(entry["tool_name"]),
                "summary": str(entry["summary"]),
                "created_at": str(entry["created_at"]),
                "status": str(entry["status"]),
                "available": str(entry["status"]) == "active",
                "paths": paths,
                "path_count": len(paths),
            }
            items.append(item)
            line = (
                f"#{item['rollback_id']} [{item['status']}] {item['source_tool']} - {item['summary']}"
            )
            if paths:
                line += f" ({item['path_count']} path{'s' if item['path_count'] != 1 else ''})"
            preview_lines.append(line)

        summary = (
            f"Loaded {len(items)} rollback entr{'ies' if len(items) != 1 else 'y'}"
            if items
            else "No rollback history for this session yet"
        )
        preview = "\n".join(preview_lines) if preview_lines else "no rollback history for this session yet"
        return {
            "entries": items,
            "count": len(items),
            "include_inactive": bool(include_inactive),
            "summary": summary,
            "preview": preview,
        }

    def preview_rollback_change(self, rollback_id: int) -> dict[str, Any]:
        if not self.session_id:
            return self._rollback_preview_unavailable(
                "Rollback is unavailable without an active chat session",
                "rollback unavailable without an active chat session",
            )

        entry = db.get_rollback_entry(self.session_id, int(rollback_id))
        if entry is None:
            return self._rollback_preview_unavailable(
                f"Rollback #{int(rollback_id)} was not found in this session",
                f"rollback #{int(rollback_id)} was not found in this session",
            )

        active_entries = db.list_rollback_entries(
            self.session_id,
            limit=500,
            include_inactive=False,
        )
        superseded_active_count = sum(
            1
            for item in active_entries
            if int(item["id"]) > int(entry["id"])
        )
        return self._preview_rollback_entry(
            entry,
            superseded_active_count=superseded_active_count,
        )

    def preview_rollback_last_change(self) -> dict[str, Any]:
        if not self.session_id:
            return self._rollback_preview_unavailable(
                "Rollback is unavailable without an active chat session",
                "rollback unavailable without an active chat session",
            )

        entry = db.get_latest_rollback_entry(self.session_id)
        if entry is None:
            return self._rollback_preview_unavailable(
                "No rollback is available for this session yet",
                "no rollback is available for this session yet",
            )
        return self._preview_rollback_entry(entry)

    def _apply_rollback_entry(
        self,
        entry: dict[str, Any],
        requested_tool: str,
    ) -> dict[str, Any]:
        status = str(entry.get("status") or "")
        if status != "active":
            raise WorkspaceError(
                f"Rollback #{int(entry['id'])} is not active anymore (status: {status})"
            )

        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        if payload.get("action") != "restore_states":
            raise WorkspaceError("Unsupported rollback payload")

        target_paths = [
            self._resolve_path(path, access="write")
            for path in self._rollback_entry_paths(entry)
        ]
        undo_snapshot_token, undo_states = self._capture_restore_states(target_paths)

        snapshot_token = payload.get("snapshot_token")
        snapshot_root = (
            self._snapshot_root_for_token(str(snapshot_token))
            if snapshot_token
            else None
        )
        states = payload.get("states") if isinstance(payload.get("states"), list) else []
        try:
            restored_paths = [
                self._restore_path_state(state, snapshot_root)
                for state in states
                if isinstance(state, dict)
            ]
        except Exception:
            self._cleanup_snapshot_token(undo_snapshot_token)
            raise

        superseded_count = 0
        if self.session_id:
            superseded_count = db.mark_rollback_entries_superseded_after(
                self.session_id,
                int(entry["id"]),
            )
        db.mark_rollback_entry_applied(int(entry["id"]))

        undo_summary = f"Undo rollback #{entry['id']} from {entry['tool_name']}"
        undo_rollback_id = self._save_restore_rollback(
            requested_tool,
            undo_summary,
            undo_snapshot_token,
            undo_states,
        )

        self._cleanup_snapshot_token(str(snapshot_token) if snapshot_token else None)
        summary = (
            f"Rolled back #{entry['id']} from {entry['tool_name']}"
            + (
                f" ({len(restored_paths)} path{'s' if len(restored_paths) != 1 else ''})"
                if restored_paths
                else ""
            )
        )
        if superseded_count > 0:
            summary += f"; superseded {superseded_count} newer rollback entr"
            summary += "ies" if superseded_count != 1 else "y"

        return {
            "ok": True,
            "rollback_id": int(entry["id"]),
            "undo_rollback_id": undo_rollback_id,
            "source_tool": str(entry["tool_name"]),
            "created_at": str(entry["created_at"]),
            "status": "applied",
            "paths": restored_paths,
            "path_count": len(restored_paths),
            "superseded_active_count": superseded_count,
            "summary": summary,
            "rolled_back_summary": str(entry["summary"]),
        }

    def rollback_last_change(self) -> dict[str, Any]:
        if not self.session_id:
            raise WorkspaceError("Rollback is unavailable without an active chat session")

        entry = db.get_latest_rollback_entry(self.session_id)
        if entry is None:
            raise WorkspaceError("No rollback is available for this session yet")
        return self._apply_rollback_entry(entry, requested_tool="rollback_last_change")

    def rollback_change(self, rollback_id: int) -> dict[str, Any]:
        if not self.session_id:
            raise WorkspaceError("Rollback is unavailable without an active chat session")

        entry = db.get_rollback_entry(self.session_id, int(rollback_id))
        if entry is None:
            raise WorkspaceError(f"Rollback #{int(rollback_id)} was not found in this session")
        return self._apply_rollback_entry(entry, requested_tool="rollback_change")

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        file_path = self._resolve_path(path, access="write")
        existed = file_path.exists()
        snapshot_token, restore_states = self._capture_restore_states([file_path])
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with file_path.open("w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        except Exception:
            self._cleanup_snapshot_token(snapshot_token)
            raise
        summary = f"Wrote {self._rel(file_path)} ({len(content.splitlines())} lines)"
        rollback_id = self._save_restore_rollback(
            "write_file",
            summary,
            snapshot_token,
            restore_states,
        )
        return {
            "path": self._rel(file_path),
            "abs_path": str(file_path),
            "exists": existed,
            "bytes_written": len(content.encode("utf-8")),
            "line_count": len(content.splitlines()),
            "rollback_id": rollback_id,
            "summary": summary,
        }

    def rename_path(self, source_path: str, target_path: str) -> dict[str, Any]:
        preview = self.preview_rename_path(source_path, target_path)
        source = self._resolve_path(source_path, access="write")
        target = self._resolve_path(target_path, access="write")
        snapshot_token, restore_states = self._capture_restore_states([source, target])
        try:
            source.rename(target)
        except Exception:
            self._cleanup_snapshot_token(snapshot_token)
            raise
        summary = f"Renamed {preview['source_path']} -> {preview['target_path']}"
        rollback_id = self._save_restore_rollback(
            "rename_path",
            summary,
            snapshot_token,
            restore_states,
        )
        return {
            "ok": True,
            "source_path": preview["source_path"],
            "target_path": preview["target_path"],
            "item_type": preview["item_type"],
            "rollback_id": rollback_id,
            "summary": summary,
        }

    def copy_path(self, source_path: str, target_path: str) -> dict[str, Any]:
        preview = self.preview_copy_path(source_path, target_path)
        source = self._resolve_path(source_path, access="read")
        target = self._resolve_path(target_path, access="write")
        snapshot_token, restore_states = self._capture_restore_states([target])
        try:
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        except Exception:
            self._cleanup_snapshot_token(snapshot_token)
            raise
        summary = f"Copied {preview['source_path']} -> {preview['target_path']}"
        rollback_id = self._save_restore_rollback(
            "copy_path",
            summary,
            snapshot_token,
            restore_states,
        )
        return {
            "ok": True,
            "source_path": preview["source_path"],
            "target_path": preview["target_path"],
            "item_type": preview["item_type"],
            "item_count": preview["item_count"],
            "rollback_id": rollback_id,
            "summary": summary,
        }

    def delete_path(self, path: str, recursive: bool = True) -> dict[str, Any]:
        preview = self.preview_delete_path(path, recursive=recursive)
        target = self._resolve_path(path, access="write")
        snapshot_token, restore_states = self._capture_restore_states([target])
        try:
            if target.is_dir():
                if recursive:
                    shutil.rmtree(target)
                else:
                    target.rmdir()
            else:
                target.unlink()
        except Exception:
            self._cleanup_snapshot_token(snapshot_token)
            raise
        summary = f"Deleted {preview['path']}"
        rollback_id = self._save_restore_rollback(
            "delete_path",
            summary,
            snapshot_token,
            restore_states,
        )
        return {
            "ok": True,
            "path": preview["path"],
            "item_type": preview["item_type"],
            "recursive": preview["recursive"],
            "item_count": preview["item_count"],
            "rollback_id": rollback_id,
            "summary": summary,
        }

    def make_directory(self, path: str) -> dict[str, Any]:
        preview = self.preview_make_directory(path)
        target = self._resolve_path(path, access="write")
        existed = target.exists()
        snapshot_token, restore_states = self._capture_restore_states([target])
        try:
            target.mkdir(parents=False, exist_ok=True)
        except Exception:
            self._cleanup_snapshot_token(snapshot_token)
            raise
        summary = (
            f"Created directory {preview['path']}"
            if not existed
            else f"Directory already existed: {preview['path']}"
        )
        rollback_id = self._save_restore_rollback(
            "make_directory",
            summary,
            snapshot_token,
            restore_states,
        )
        return {
            "ok": True,
            "path": preview["path"],
            "created": not existed,
            "rollback_id": rollback_id,
            "summary": summary,
        }

    def run_command(
        self,
        command: str,
        cwd: str | None = None,
        timeout_ms: int = 120000,
    ) -> dict[str, Any]:
        if not command or not command.strip():
            raise WorkspaceError("command is required")

        workdir = self.root if not cwd else self._resolve_path(cwd, access="command")
        if not workdir.exists():
            raise WorkspaceError(self._not_found_message("Working directory", workdir))
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
                "summary": self._command_summary(
                    returncode=None,
                    timed_out=True,
                    duration_ms=duration_ms,
                    stdout=stdout,
                    stderr=stderr,
                ),
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
            "summary": self._command_summary(
                returncode=proc.returncode,
                timed_out=timed_out,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
            ),
        }
