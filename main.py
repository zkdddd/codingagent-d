import argparse
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent / "crash.log"
PROJECT_ROOT = Path(__file__).resolve().parent

DEV_RELOAD_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
}

DEV_RELOAD_WATCH_NAMES = {".env", ".env.example", "requirements.txt"}


def log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='milliseconds')}] {msg}\n")
            f.flush()
    except Exception:
        pass


def write_crash(exc_type, exc_value, exc_tb):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"CRASH @ {datetime.now().isoformat()}\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write(f"argv: {sys.argv}\n")
            f.write("-" * 60 + "\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
            f.flush()
    except Exception:
        pass


def install_excepthook():
    def handler(t, v, tb):
        write_crash(t, v, tb)
        sys.__excepthook__(t, v, tb)

    sys.excepthook = handler


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def parse_cli_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--dev-reload",
        action="store_true",
        default=_env_flag("KAGENT_DEV_RELOAD", False),
        help="Restart the app when source files change.",
    )
    parser.add_argument(
        "--reload-interval-ms",
        type=int,
        default=_env_int("KAGENT_DEV_RELOAD_INTERVAL_MS", 1000),
        help="Polling interval for dev reload in milliseconds.",
    )
    args, remaining = parser.parse_known_args(argv[1:])
    return args, [argv[0], *remaining]


class DevReloadWatcher:
    def __init__(self, root: Path, interval_ms: int = 1000):
        self.root = root.resolve()
        self.interval_ms = max(250, int(interval_ms))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="kagent-dev-reload", daemon=True)
        self._snapshot = self._snapshot_files()
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        log(f"DEV RELOAD enabled: watching {self.root} every {self.interval_ms}ms")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _is_watched(self, path: Path) -> bool:
        name = path.name.lower()
        return path.suffix.lower() == ".py" or name in DEV_RELOAD_WATCH_NAMES

    def _walk_files(self):
        for current_root, dirs, files in os.walk(self.root):
            dirs[:] = [
                d
                for d in sorted(dirs)
                if d not in DEV_RELOAD_IGNORE_DIRS and not d.startswith(".")
            ]
            current = Path(current_root)
            for name in sorted(files):
                candidate = current / name
                if self._is_watched(candidate):
                    yield candidate

    def _snapshot_files(self) -> dict[str, tuple[int, int]]:
        snapshot: dict[str, tuple[int, int]] = {}
        for path in self._walk_files():
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[path.relative_to(self.root).as_posix()] = (stat.st_mtime_ns, stat.st_size)
        return snapshot

    @staticmethod
    def _changed_paths(
        previous: dict[str, tuple[int, int]],
        current: dict[str, tuple[int, int]],
    ) -> list[str]:
        changed: list[str] = []
        for rel in sorted(set(previous) | set(current)):
            if previous.get(rel) != current.get(rel):
                changed.append(rel)
        return changed

    def _loop(self):
        while not self._stop.wait(self.interval_ms / 1000.0):
            current = self._snapshot_files()
            if current == self._snapshot:
                continue

            changed = self._changed_paths(self._snapshot, current)
            self._snapshot = current
            changed_text = ", ".join(changed[:5]) if changed else "unknown"
            if len(changed) > 5:
                changed_text += f" (+{len(changed) - 5} more)"
            log(f"DEV RELOAD detected change(s): {changed_text}")

            try:
                sys.stdout.flush()
                sys.stderr.flush()
                os.execv(sys.executable, [sys.executable, *sys.argv])
            except Exception as exc:
                log(f"DEV RELOAD restart failed: {exc!r}")
            return


def main():
    cli_args, qt_argv = parse_cli_args(sys.argv)
    dev_reload = cli_args.dev_reload
    reload_interval_ms = max(250, int(cli_args.reload_interval_ms))

    # 清空旧日志
    try:
        if dev_reload:
            log(f"{'=' * 24} DEV RELOAD START @ {datetime.now().isoformat()} {'=' * 24}")
        else:
            LOG_FILE.write_text(f"kagent startup @ {datetime.now().isoformat()}\n", encoding="utf-8")
    except Exception:
        pass

    log(f"Python: {sys.version}")
    log(f"Platform: {sys.platform}")
    log(f"argv: {sys.argv}")
    log(f"cwd: {Path.cwd()}")
    if dev_reload:
        log(f"Dev reload interval: {reload_interval_ms}ms")

    install_excepthook()

    try:
        log("STEP 1: importing dotenv")
        from dotenv import load_dotenv

        load_dotenv()
        log("STEP 2: importing PyQt6.QtWidgets")
        from PyQt6.QtWidgets import QApplication, QMessageBox

        log("STEP 3: importing kagent.config")
        from kagent.config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL

        log(f"  config: model={MODEL}, base_url={OPENAI_BASE_URL}, key={'set' if OPENAI_API_KEY else 'EMPTY'}")
        log("STEP 4: importing kagent.db")
        from kagent import db

        log("STEP 5: init_db")
        db.init_db()
        log("STEP 6: creating QApplication")
        app = QApplication(qt_argv)
        app.setApplicationName("kagent")
        log("STEP 7: importing ChatWindow")
        from kagent.ui.main_window import ChatWindow

        log("STEP 8: creating ChatWindow")
        win = ChatWindow()
        log("STEP 9: showing window")
        win.show()

        dev_watcher = None
        if dev_reload:
            log("STEP 9A: starting dev reload watcher")
            dev_watcher = DevReloadWatcher(PROJECT_ROOT, reload_interval_ms)
            dev_watcher.start()
            app.aboutToQuit.connect(dev_watcher.stop)
            app._dev_reload_watcher = dev_watcher  # keep alive for the app lifetime

        log("STEP 10: entering event loop")
        sys.exit(app.exec())
    except Exception:
        traceback.print_exc()
        write_crash(*sys.exc_info())
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is None:
                QApplication(sys.argv)
            QMessageBox.critical(None, "kagent 启动失败", traceback.format_exc())
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
