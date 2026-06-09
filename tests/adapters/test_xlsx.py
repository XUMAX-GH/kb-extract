import pytest

from kb_extract.adapters.xlsx import XlsxAdapter
from kb_extract.hardness import assert_invariants

from ._fixtures import make_xlsx


@pytest.mark.disable_socket
def test_xlsx_adapter_sheet_per_level1_section(tmp_path):
    src = make_xlsx(tmp_path / "wb.xlsx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = XlsxAdapter().extract(src, out_dir)
    # Two sheets → two L1 children
    assert len(result.index.children) == 2
    titles = [c.title for c in result.index.children]
    assert "Summary" in titles and "Details" in titles


@pytest.mark.disable_socket
def test_xlsx_adapter_table_block_with_rows_json(tmp_path):
    src = make_xlsx(tmp_path / "wb.xlsx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = XlsxAdapter().extract(src, out_dir)
    # Summary sheet has 3 rows x 2 cols
    summary_tables = [
        t for t in result.tables if t.rows_json and t.rows_json[0] == ("metric", "value")
    ]
    assert summary_tables, "expected Summary table extracted"


@pytest.mark.disable_socket
def test_xlsx_adapter_passes_hardness(tmp_path):
    src = make_xlsx(tmp_path / "wb.xlsx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = XlsxAdapter().extract(src, out_dir)
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)
