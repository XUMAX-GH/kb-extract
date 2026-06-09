import pytest

from kb_extract.adapters.pptx import PptxAdapter
from kb_extract.hardness import assert_invariants

from ._fixtures import make_pptx


@pytest.mark.disable_socket
def test_pptx_adapter_one_section_per_slide(tmp_path):
    src = make_pptx(tmp_path / "deck.pptx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PptxAdapter().extract(src, out_dir)
    assert len(result.index.children) == 2
    titles = [c.title for c in result.index.children]
    assert "First Slide" in titles and "Second Slide" in titles


@pytest.mark.disable_socket
def test_pptx_adapter_includes_speaker_notes_as_blockquote(tmp_path):
    src = make_pptx(tmp_path / "deck.pptx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PptxAdapter().extract(src, out_dir)
    assert "> Note: presenter note one" in result.markdown


@pytest.mark.disable_socket
def test_pptx_adapter_passes_hardness(tmp_path):
    src = make_pptx(tmp_path / "deck.pptx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PptxAdapter().extract(src, out_dir)
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)
