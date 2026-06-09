"""Helpers shared by all adapters."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ..contracts import ExtractionMeta

OutlineSource = Literal["bookmark", "heading_style", "docling_layout", "page_fallback"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_meta(
    *,
    src: Path,
    adapter_name: str,
    adapter_version: str,
    tool_versions: dict[str, str],
    outline_source: OutlineSource,
    status: str = "ok",
    warnings: tuple[str, ...] = (),
    skipped_reasons: tuple[str, ...] = (),
    extracted_at_iso: str | None = None,
) -> ExtractionMeta:
    stat = src.stat()
    src_bytes = src.read_bytes()
    return ExtractionMeta(
        source_path=src.name,
        source_sha256=sha256_bytes(src_bytes),
        source_bytes=len(src_bytes),
        source_mtime_iso=datetime.fromtimestamp(
            stat.st_mtime, tz=UTC
        ).isoformat(),
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        tool_versions=tool_versions,
        extracted_at_iso=extracted_at_iso or "1970-01-01T00:00:00+00:00",
        outline_source=outline_source,
        status=status,  # type: ignore[arg-type]
        warnings=warnings,
        skipped_reasons=skipped_reasons,
    )
