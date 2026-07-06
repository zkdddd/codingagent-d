import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator

from .config import DB_PATH

_lock = threading.Lock()


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)"
        )


def create_session(session_id: str, title: str = "新对话") -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO sessions (id, title) VALUES (?, ?)",
            (session_id, title),
        )


def rename_session(session_id: str, title: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "UPDATE sessions SET title = ? WHERE id = ?",
            (title, session_id),
        )


def list_sessions() -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT id, title, created_at FROM sessions ORDER BY created_at DESC"
        ).fetchall()
        return [{"id": r["id"], "title": r["title"], "created_at": r["created_at"]} for r in rows]


def delete_session(session_id: str) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def save_message(session_id: str, role: str, content: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )


def get_messages(session_id: str) -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
            for r in rows
        ]
