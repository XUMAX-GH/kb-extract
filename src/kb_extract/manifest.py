"""Per-project SQLite manifest of extracted sources. See spec §5.4."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .contracts import ExtractionMeta

Status = Literal["ok", "partial", "failed", "skipped"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_path        TEXT PRIMARY KEY,
    source_sha256      TEXT,
    source_bytes       INTEGER,
    source_mtime_iso   TEXT,
    adapter_name       TEXT,
    adapter_version    TEXT,
    tool_versions_json TEXT,
    extracted_at_iso   TEXT,
    outline_source     TEXT,
    status             TEXT NOT NULL,
    warnings_json      TEXT,
    skipped_reason     TEXT,
    error_repr         TEXT,
    output_sha256      TEXT
);
"""


@dataclass(frozen=True, slots=True)
class ManifestRow:
    source_path: str
    source_sha256: str | None
    source_bytes: int | None
    source_mtime_iso: str | None
    adapter_name: str | None
    adapter_version: str | None
    tool_versions: dict[str, str]
    extracted_at_iso: str | None
    outline_source: str | None
    status: Status
    warnings: tuple[str, ...]
    skipped_reason: str | None
    error_repr: str | None
    output_sha256: str | None


class Manifest:
    """Wrapper around SQLite manifest file."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def _key(self, src: Path, meta: ExtractionMeta | None = None) -> str:
        """Extract key for storage/lookup.
        
        Prefers metadata's source_path if provided (for consistency with stored data),
        falls back to extracting relative path from src.
        """
        if meta is not None:
            return meta.source_path
        # Extract relative path from src (last 2+ components) using posix format
        parts = src.parts
        if len(parts) >= 2:
            return Path(*parts[-2:]).as_posix()
        return src.as_posix()

    def upsert(
        self,
        src: Path,
        meta: ExtractionMeta,
        *,
        output_sha256: str,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(
                    source_path, source_sha256, source_bytes, source_mtime_iso,
                    adapter_name, adapter_version, tool_versions_json,
                    extracted_at_iso, outline_source, status, warnings_json,
                    skipped_reason, error_repr, output_sha256
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_path) DO UPDATE SET
                    source_sha256=excluded.source_sha256,
                    source_bytes=excluded.source_bytes,
                    source_mtime_iso=excluded.source_mtime_iso,
                    adapter_name=excluded.adapter_name,
                    adapter_version=excluded.adapter_version,
                    tool_versions_json=excluded.tool_versions_json,
                    extracted_at_iso=excluded.extracted_at_iso,
                    outline_source=excluded.outline_source,
                    status=excluded.status,
                    warnings_json=excluded.warnings_json,
                    skipped_reason=NULL,
                    error_repr=NULL,
                    output_sha256=excluded.output_sha256
                """,
                (
                    self._key(src, meta),
                    meta.source_sha256,
                    meta.source_bytes,
                    meta.source_mtime_iso,
                    meta.adapter_name,
                    meta.adapter_version,
                    json.dumps(meta.tool_versions, sort_keys=True),
                    meta.extracted_at_iso,
                    meta.outline_source,
                    meta.status,
                    json.dumps(list(meta.warnings), sort_keys=True),
                    None,
                    None,
                    output_sha256,
                ),
            )

    def mark_skipped(self, src: Path, reason: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(source_path, status, skipped_reason)
                VALUES (?,?,?)
                ON CONFLICT(source_path) DO UPDATE SET
                    status='skipped', skipped_reason=excluded.skipped_reason
                """,
                (self._key(src), "skipped", reason),
            )

    def mark_failed(self, src: Path, error_repr: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(source_path, status, error_repr)
                VALUES (?,?,?)
                ON CONFLICT(source_path) DO UPDATE SET
                    status='failed', error_repr=excluded.error_repr
                """,
                (self._key(src), "failed", error_repr),
            )

    def get(self, src: Path) -> ManifestRow | None:
        cur = self.conn.execute(
            "SELECT * FROM sources WHERE source_path = ?", (self._key(src),)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dc(row, cur.description)

    def iter(self) -> Iterator[ManifestRow]:
        cur = self.conn.execute("SELECT * FROM sources ORDER BY source_path")
        desc = cur.description
        for row in cur:
            yield self._row_to_dc(row, desc)

    @staticmethod
    def _row_to_dc(row, desc) -> ManifestRow:
        d = {desc[i][0]: row[i] for i in range(len(desc))}
        tool_versions = json.loads(d.get("tool_versions_json") or "{}")
        warnings = tuple(json.loads(d.get("warnings_json") or "[]"))
        return ManifestRow(
            source_path=d["source_path"],
            source_sha256=d.get("source_sha256"),
            source_bytes=d.get("source_bytes"),
            source_mtime_iso=d.get("source_mtime_iso"),
            adapter_name=d.get("adapter_name"),
            adapter_version=d.get("adapter_version"),
            tool_versions=tool_versions,
            extracted_at_iso=d.get("extracted_at_iso"),
            outline_source=d.get("outline_source"),
            status=d["status"],
            warnings=warnings,
            skipped_reason=d.get("skipped_reason"),
            error_repr=d.get("error_repr"),
            output_sha256=d.get("output_sha256"),
        )
