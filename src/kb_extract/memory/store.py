"""Persistent memory store (sqlite, WAL).

Schema v1:
  preferences(key TEXT PK, value TEXT, updated_at TEXT)
  query_history(id INTEGER PK, ts TEXT, project_root TEXT, command TEXT,
                args_json TEXT, exit_code INTEGER, summary TEXT)

H20: BEGIN IMMEDIATE + WAL mode so concurrent writes from multiple kb
invocations don't corrupt the DB.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    id: int
    ts: str
    project_root: str
    command: str
    args_json: str
    exit_code: int
    summary: str


def default_memory_path() -> Path:
    """Resolve the memory.db path with env override.

    Order:
      1. $KB_EXTRACT_HOME/memory.db
      2. ~/.kb-extract/memory.db
    """
    override = os.environ.get("KB_EXTRACT_HOME")
    if override:
        return Path(override) / "memory.db"
    return Path.home() / ".kb-extract" / "memory.db"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class MemoryStore:
    """Sqlite-backed store. Safe for concurrent processes via WAL + IMMEDIATE."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = (path or default_memory_path()).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    # ---- lifecycle ----
    def __enter__(self) -> MemoryStore:
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def open(self) -> None:
        self._conn = sqlite3.connect(self._path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def path(self) -> Path:
        return self._path

    # ---- schema ----
    def _ensure_schema(self) -> None:
        assert self._conn is not None
        self._conn.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                project_root TEXT NOT NULL,
                command TEXT NOT NULL,
                args_json TEXT NOT NULL,
                exit_code INTEGER NOT NULL,
                summary TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_history_project
                ON query_history(project_root, ts);
            COMMIT;
            """
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO schema_meta(key,value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

    # ---- preferences ----
    def set_pref(self, key: str, value: str) -> None:
        assert self._conn is not None
        with _immediate_txn(self._conn):
            self._conn.execute(
                "INSERT INTO preferences(key,value,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (key, value, _now_iso()),
            )

    def get_pref(self, key: str) -> str | None:
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT value FROM preferences WHERE key=?", (key,)
        ).fetchone()
        return None if row is None else row[0]

    def list_prefs(self) -> dict[str, str]:
        assert self._conn is not None
        return {
            r[0]: r[1]
            for r in self._conn.execute(
                "SELECT key, value FROM preferences ORDER BY key"
            )
        }

    def forget_pref(self, key: str) -> bool:
        assert self._conn is not None
        with _immediate_txn(self._conn):
            cur = self._conn.execute("DELETE FROM preferences WHERE key=?", (key,))
            return cur.rowcount > 0

    # ---- history ----
    def record(
        self,
        *,
        project_root: str,
        command: str,
        args: dict | None = None,
        exit_code: int,
        summary: str | None = None,
    ) -> int:
        assert self._conn is not None
        args_json = json.dumps(args or {}, ensure_ascii=False, sort_keys=True)
        with _immediate_txn(self._conn):
            cur = self._conn.execute(
                "INSERT INTO query_history(ts,project_root,command,args_json,exit_code,summary) "
                "VALUES(?,?,?,?,?,?)",
                (_now_iso(), project_root, command, args_json, exit_code, summary),
            )
        return int(cur.lastrowid or 0)

    def recall(
        self,
        *,
        project_root: str | None = None,
        command: str | None = None,
        limit: int = 20,
    ) -> list[HistoryRecord]:
        assert self._conn is not None
        conds: list[str] = []
        params: list[object] = []
        if project_root:
            conds.append("project_root = ?")
            params.append(project_root)
        if command:
            conds.append("command = ?")
            params.append(command)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        params.append(int(limit))
        rows = self._conn.execute(
            f"SELECT id, ts, project_root, command, args_json, exit_code, summary "
            f"FROM query_history {where} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
        return [
            HistoryRecord(
                id=r[0], ts=r[1], project_root=r[2], command=r[3],
                args_json=r[4], exit_code=r[5], summary=r[6] or "",
            )
            for r in rows
        ]


class _immediate_txn:
    """Context manager wrapping BEGIN IMMEDIATE / COMMIT / ROLLBACK."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __enter__(self) -> None:
        self._conn.execute("BEGIN IMMEDIATE")

    def __exit__(self, exc_type, *_a) -> None:
        if exc_type is None:
            self._conn.execute("COMMIT")
        else:
            self._conn.execute("ROLLBACK")


# Convenience for callers that just want a one-shot record
def quick_record(
    *,
    project_root: str,
    command: str,
    args: dict | None = None,
    exit_code: int,
    summary: str | None = None,
) -> None:
    with MemoryStore() as m:
        m.record(
            project_root=project_root,
            command=command,
            args=args,
            exit_code=exit_code,
            summary=summary,
        )


def history_to_dicts(records: Iterable[HistoryRecord]) -> Iterator[dict]:
    for r in records:
        yield asdict(r)
