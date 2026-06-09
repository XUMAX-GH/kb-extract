import pytest

from kb_extract.adapters.docx import DocxAdapter
from kb_extract.hardness import assert_invariants

from ._fixtures import make_docx


@pytest.mark.disable_socket
def test_docx_adapter_extracts_headings_and_paragraphs(tmp_path):
    src = make_docx(tmp_path / "test.docx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = DocxAdapter().extract(src, out_dir)
    assert "# Chapter 1" in result.markdown
    assert "## Section 1.1" in result.markdown
    assert "First paragraph in chapter 1." in result.markdown


@pytest.mark.disable_socket
def test_docx_adapter_extracts_table_as_markdown_and_rows_json(tmp_path):
    src = make_docx(tmp_path / "test.docx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = DocxAdapter().extract(src, out_dir)
    assert "| col A | col B |" in result.markdown
    assert any(t.rows_json[0] == ("col A", "col B") for t in result.tables)


@pytest.mark.disable_socket
def test_docx_adapter_passes_hardness_invariants(tmp_path):
    src = make_docx(tmp_path / "test.docx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = DocxAdapter().extract(src, out_dir)
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)
