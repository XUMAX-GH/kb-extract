import pytest

from kb_extract.adapters.pdf_docling import PdfDoclingAdapter
from kb_extract.hardness import assert_invariants

from ._fixtures import make_pdf


@pytest.mark.disable_socket
@pytest.mark.slow
def test_pdf_adapter_uses_bookmarks_when_available(tmp_path):
    src = make_pdf(tmp_path / "doc.pdf")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PdfDoclingAdapter().extract(src, out_dir)
    titles = [c.title for c in result.index.children]
    assert "Chapter 1" in titles and "Chapter 2" in titles
    assert result.meta.outline_source == "bookmark"


@pytest.mark.disable_socket
@pytest.mark.slow
def test_pdf_adapter_passes_hardness(tmp_path):
    src = make_pdf(tmp_path / "doc.pdf")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PdfDoclingAdapter().extract(src, out_dir)
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)
