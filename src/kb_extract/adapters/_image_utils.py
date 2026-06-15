"""Shared image extraction helpers for v0.8.0 parser adapters.

Detects image format from magic bytes (PNG/JPG/GIF/BMP) and writes the
blob to ``<root>/assets/<prefix>_<index>.<ext>``. Images smaller than
``MIN_IMAGE_BYTES`` (1 KiB) are skipped — these are typically decorative
icons or rendering artefacts, not content. Returns the markdown-relative
path on success, ``None`` when skipped.

Pure stdlib, deterministic.
"""
from __future__ import annotations

from pathlib import Path

MIN_IMAGE_BYTES = 1024


def detect_image_format(blob: bytes) -> str | None:
    """Return ``"png"`` / ``"jpg"`` / ``"gif"`` / ``"bmp"`` or ``None``."""
    if len(blob) < 4:
        return None
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if blob[:2] == b"\xff\xd8":
        return "jpg"
    if blob[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if blob[:2] == b"BM":
        return "bmp"
    return None


def save_image(
    blob: bytes,
    root: Path,
    *,
    prefix: str,
    index: int,
) -> str | None:
    """Save ``blob`` to ``root/assets/<prefix>_<index>.<ext>``.

    - Returns ``"assets/<prefix>_<index>.<ext>"`` (markdown-relative path)
      when the image is kept.
    - Returns ``None`` when the format is unknown OR the blob is smaller
      than :data:`MIN_IMAGE_BYTES` (decorative / rendering artefacts).
    - Creates ``root/assets/`` lazily; never touches the filesystem when
      the image is skipped.
    """
    if len(blob) < MIN_IMAGE_BYTES:
        return None
    fmt = detect_image_format(blob)
    if fmt is None:
        return None

    assets_dir = root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{index}.{fmt}"
    (assets_dir / filename).write_bytes(blob)
    return f"assets/{filename}"
