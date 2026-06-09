import io

import pytest
from PIL import Image as PILImage

from kb_extract.adapters.image import ImageAdapter
from kb_extract.hardness import assert_invariants


def _png_bytes(w=4, h=3, color=(255, 0, 0)) -> bytes:
    img = PILImage.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.disable_socket
def test_image_adapter_produces_valid_extraction(tmp_path):
    src = tmp_path / "photo.png"
    src.write_bytes(_png_bytes())
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    a = ImageAdapter()
    result = a.extract(src, out_dir)
    # main.md has single section with anchor; image referenced
    assert "assets/photo.png" in result.markdown
    assert result.assets and result.assets[0].rel_path == "assets/photo.png"
    # Asset file actually copied
    assert (out_dir / "assets" / "photo.png").exists()
    assert_invariants(result, src, out_dir, total_pages=1)


@pytest.mark.disable_socket
def test_image_adapter_jpg_extension(tmp_path):
    src = tmp_path / "p.jpg"
    img = PILImage.new("RGB", (5, 5), (0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    src.write_bytes(buf.getvalue())
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    a = ImageAdapter()
    result = a.extract(src, out_dir)
    assert "assets/p.jpg" in result.markdown
    assert_invariants(result, src, out_dir, total_pages=1)
