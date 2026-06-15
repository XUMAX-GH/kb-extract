"""Tests for H22 image-integrity hardness check (v0.8.0)."""
from __future__ import annotations

from pathlib import Path

import pytest

from kb_extract.errors import HardnessViolation
from kb_extract.hardness import check_h22_image_integrity

pytestmark = pytest.mark.disable_socket


def _png_bytes() -> bytes:
    """Minimal but valid PNG: header + IHDR + IDAT + IEND."""
    import struct
    import zlib

    def chunk(typ: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(typ + data)
        return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def test_h22_passes_when_no_image_references(tmp_path: Path) -> None:
    check_h22_image_integrity("no images here", tmp_path)  # no-op


def test_h22_passes_for_valid_png(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "good.png").write_bytes(_png_bytes())
    md = "see ![](assets/good.png) for details"
    check_h22_image_integrity(md, tmp_path)  # no raise


def test_h22_raises_when_referenced_file_is_missing(tmp_path: Path) -> None:
    md = "see ![](assets/missing.png)"
    with pytest.raises(HardnessViolation) as excinfo:
        check_h22_image_integrity(md, tmp_path)
    assert excinfo.value.invariant == "H22"


def test_h22_raises_when_file_has_no_image_magic(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "fake.png").write_bytes(b"this is not a png file at all")
    md = "see ![](assets/fake.png)"
    with pytest.raises(HardnessViolation) as excinfo:
        check_h22_image_integrity(md, tmp_path)
    assert excinfo.value.invariant == "H22"
    assert "fake.png" in excinfo.value.detail


def test_h22_inspects_all_references(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "ok.png").write_bytes(_png_bytes())
    (tmp_path / "assets" / "bad.png").write_bytes(b"junk")
    md = "![](assets/ok.png) and ![](assets/bad.png)"
    with pytest.raises(HardnessViolation):
        check_h22_image_integrity(md, tmp_path)
