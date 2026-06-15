"""Tests for adapters._image_utils (v0.8.0 parser v2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from kb_extract.adapters._image_utils import (
    MIN_IMAGE_BYTES,
    detect_image_format,
    save_image,
)

pytestmark = pytest.mark.disable_socket


# Magic bytes for each supported format
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPG_MAGIC = b"\xff\xd8\xff\xe0"
GIF_MAGIC = b"GIF89a"
BMP_MAGIC = b"BM"


def _pad(magic: bytes, size: int) -> bytes:
    """Pad magic bytes with zeroes to reach `size` total bytes."""
    return magic + b"\x00" * (size - len(magic))


# ---- detect_image_format ----------------------------------------------------


def test_detect_png() -> None:
    assert detect_image_format(_pad(PNG_MAGIC, 2048)) == "png"


def test_detect_jpg() -> None:
    assert detect_image_format(_pad(JPG_MAGIC, 2048)) == "jpg"


def test_detect_gif() -> None:
    assert detect_image_format(_pad(GIF_MAGIC, 2048)) == "gif"


def test_detect_bmp() -> None:
    assert detect_image_format(_pad(BMP_MAGIC, 2048)) == "bmp"


def test_detect_unknown_returns_none() -> None:
    assert detect_image_format(b"\x00\x00\x00\x00deadbeef" + b"\x00" * 100) is None


def test_detect_too_short_returns_none() -> None:
    assert detect_image_format(b"\x89PN") is None
    assert detect_image_format(b"") is None


# ---- save_image -------------------------------------------------------------


def test_save_png_creates_file_with_correct_name(tmp_path: Path) -> None:
    blob = _pad(PNG_MAGIC, 2048)
    rel = save_image(blob, tmp_path, prefix="img", index=1)
    assert rel == "assets/img_1.png"
    saved = tmp_path / "assets" / "img_1.png"
    assert saved.is_file()
    assert saved.read_bytes() == blob


def test_save_jpg(tmp_path: Path) -> None:
    blob = _pad(JPG_MAGIC, 4096)
    rel = save_image(blob, tmp_path, prefix="slide_3_img", index=2)
    assert rel == "assets/slide_3_img_2.jpg"


def test_save_skips_small_image(tmp_path: Path) -> None:
    blob = _pad(PNG_MAGIC, MIN_IMAGE_BYTES - 1)
    rel = save_image(blob, tmp_path, prefix="img", index=1)
    assert rel is None
    assert not (tmp_path / "assets").exists()


def test_save_skips_unknown_format(tmp_path: Path) -> None:
    blob = b"\x00" * 4096
    rel = save_image(blob, tmp_path, prefix="img", index=1)
    assert rel is None


def test_save_creates_assets_dir_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "kb" / "doc"
    target.mkdir(parents=True)
    blob = _pad(PNG_MAGIC, 2048)
    rel = save_image(blob, target, prefix="img", index=5)
    assert rel == "assets/img_5.png"
    assert (target / "assets" / "img_5.png").is_file()


def test_save_deterministic_same_input_same_output(tmp_path: Path) -> None:
    blob = _pad(PNG_MAGIC, 2048)
    rel1 = save_image(blob, tmp_path, prefix="x", index=7)
    rel2 = save_image(blob, tmp_path, prefix="x", index=7)
    assert rel1 == rel2 == "assets/x_7.png"


def test_save_uses_min_image_bytes_threshold_inclusive(tmp_path: Path) -> None:
    """Exactly MIN_IMAGE_BYTES should be saved (boundary is inclusive)."""
    blob = _pad(PNG_MAGIC, MIN_IMAGE_BYTES)
    rel = save_image(blob, tmp_path, prefix="img", index=1)
    assert rel == "assets/img_1.png"
