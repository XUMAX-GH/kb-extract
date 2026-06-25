"""Per-project SQLite manifest for the kb source layer (SP-2).

Physically separate from extract's manifest.sqlite; this file lives at
kb/source.manifest.sqlite and is never touched by `kb extract`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Status = Literal["ok", "failed", "skipped"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    key                TEXT PRIMARY KEY,
    source_path        TEXT,
    source_sha256      TEXT,
    source_bytes       INTEGER,
    source_mtime_iso   TEXT,
    markitdown_version TEXT,
    source_md_sha256   TEXT,
    images_stripped    INTEGER,
    pn_redacted        INTEGER,
    policy_sha256      TEXT,
    status             TEXT NOT NULL,
    error_repr         TEXT,
    generated_at_iso   TEXT
);
"""


@dataclass(frozen=True, slots=True)
class SourceRow:
    source_path: str
    source_sha256: str | None
    source_bytes: int | None
    source_mtime_iso: str | None
    markitdown_version: str | None
    source_md_sha256: str | None
    images_stripped: int | None
    pn_redacted: int | None
    policy_sha256: str | None
    status: Status
    error_repr: str | None
    generated_at_iso: str | None


class SourceManifest:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def _key(self, src: Path) -> str:
        return src.resolve().as_posix()

    def upsert_ok(
        self,
        src: Path,
        *,
        source_sha256: str,
        source_bytes: int,
        source_mtime_iso: str,
        markitdown_version: str,
        source_md_sha256: str,
        images_stripped: int,
        pn_redacted: int,
        policy_sha256: str | None,
        generated_at_iso: str,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(
                    key, source_path, source_sha256, source_bytes,
                    source_mtime_iso, markitdown_version, source_md_sha256,
                    images_stripped, pn_redacted, policy_sha256, status,
                    error_repr, generated_at_iso
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    source_path=excluded.source_path,
                    source_sha256=excluded.source_sha256,
                    source_bytes=excluded.source_bytes,
                    source_mtime_iso=excluded.source_mtime_iso,
                    markitdown_version=excluded.markitdown_version,
                    source_md_sha256=excluded.source_md_sha256,
                    images_stripped=excluded.images_stripped,
                    pn_redacted=excluded.pn_redacted,
                    policy_sha256=excluded.policy_sha256,
                    status='ok',
                    error_repr=NULL,
                    generated_at_iso=excluded.generated_at_iso
                """,
                (
                    self._key(src), src.resolve().as_posix(), source_sha256,
                    source_bytes, source_mtime_iso, markitdown_version,
                    source_md_sha256, images_stripped, pn_redacted,
                    policy_sha256, "ok", None, generated_at_iso,
                ),
            )

    def mark_failed(self, src: Path, error_repr: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(key, source_path, status, error_repr)
                VALUES (?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    status='failed', error_repr=excluded.error_repr
                """,
                (self._key(src), src.resolve().as_posix(), "failed", error_repr),
            )

    def mark_skipped(self, src: Path, reason: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(key, source_path, status, error_repr)
                VALUES (?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    status='skipped', error_repr=excluded.error_repr
                """,
                (self._key(src), src.resolve().as_posix(), "skipped", reason),
            )

    def get(self, src: Path) -> SourceRow | None:
        cur = self.conn.execute(
            "SELECT * FROM sources WHERE key = ?", (self._key(src),)
        )
        row = cur.fetchone()
        if row is None:
            return None
        d = {cur.description[i][0]: row[i] for i in range(len(cur.description))}
        return SourceRow(
            source_path=d["source_path"],
            source_sha256=d.get("source_sha256"),
            source_bytes=d.get("source_bytes"),
            source_mtime_iso=d.get("source_mtime_iso"),
            markitdown_version=d.get("markitdown_version"),
            source_md_sha256=d.get("source_md_sha256"),
            images_stripped=d.get("images_stripped"),
            pn_redacted=d.get("pn_redacted"),
            policy_sha256=d.get("policy_sha256"),
            status=d["status"],
            error_repr=d.get("error_repr"),
            generated_at_iso=d.get("generated_at_iso"),
        )
