from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DB_PATH, ensure_dirs


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    ensure_dirs()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_user_db() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                chat_id TEXT PRIMARY KEY,
                resume TEXT NOT NULL DEFAULT '',
                criteria TEXT NOT NULL DEFAULT '',
                last_report TEXT NOT NULL DEFAULT '',
                pending_action TEXT NOT NULL DEFAULT '',
                trace TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )


def empty_user() -> dict[str, Any]:
    return {"resume": "", "criteria": "", "updated_at": "", "last_report": "", "pending_action": "", "trace": []}


def load_user(chat_id: int | str) -> dict[str, Any]:
    init_user_db()
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM user_profiles WHERE chat_id = ?",
            (str(chat_id),),
        ).fetchone()
    if row is None:
        return empty_user()
    return {
        "resume": row["resume"],
        "criteria": row["criteria"],
        "updated_at": row["updated_at"],
        "last_report": row["last_report"],
        "pending_action": row["pending_action"],
        "trace": [line for line in row["trace"].splitlines() if line],
    }


def save_user(chat_id: int | str, data: dict[str, Any]) -> None:
    init_user_db()
    trace = data.get("trace", [])
    if isinstance(trace, list):
        trace_text = "\n".join(str(item) for item in trace)
    else:
        trace_text = str(trace or "")
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO user_profiles (
                chat_id, resume, criteria, last_report, pending_action, trace, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                resume = excluded.resume,
                criteria = excluded.criteria,
                last_report = excluded.last_report,
                pending_action = excluded.pending_action,
                trace = excluded.trace,
                updated_at = excluded.updated_at
            """,
            (
                str(chat_id),
                str(data.get("resume", "")),
                str(data.get("criteria", "")),
                str(data.get("last_report", "")),
                str(data.get("pending_action", "")),
                trace_text,
                now_stamp(),
            ),
        )


def reset_user(chat_id: int | str) -> None:
    init_user_db()
    with connect() as connection:
        connection.execute("DELETE FROM user_profiles WHERE chat_id = ?", (str(chat_id),))


class RunLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.events: list[str] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def log(self, message: str) -> None:
        line = f"[{now_stamp()}] {message}"
        self.events.append(line)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
