"""Performance benchmark with 1.5x regression gate (spec §9)."""

import json
import time
from pathlib import Path

import pytest


def _bench_pdf_extract(tmp_path: Path) -> float:
    """Time extraction of a synthetic 100-page PDF."""
    import fitz

    src = tmp_path / "big.pdf"
    doc = fitz.open()
    for i in range(100):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i+1}\n" + ("Lorem ipsum dolor sit amet. " * 20))
    doc.set_toc([[1, f"Section {i+1}", i+1] for i in range(10)])
    doc.save(str(src))
    doc.close()

    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    from kb_extract.adapters.pdf_docling import PdfDoclingAdapter
    a = PdfDoclingAdapter()
    t0 = time.perf_counter()
    a.extract(src, out_dir)
    return time.perf_counter() - t0


@pytest.mark.perf
@pytest.mark.slow
def test_pdf_extract_100_pages_within_1_5x_baseline(tmp_path):
    baseline_path = Path(__file__).resolve().parent / "fixtures" / "perf-baseline.json"
    elapsed = _bench_pdf_extract(tmp_path)
    if not baseline_path.exists():
        # First-ever run records the baseline; subsequent runs gate against it.
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps({"pdf_100_pages_sec": elapsed}, indent=2))
        pytest.skip(f"recorded initial baseline: {elapsed:.2f}s")
    baseline = json.loads(baseline_path.read_text())["pdf_100_pages_sec"]
    limit = baseline * 1.5
    assert elapsed <= limit, (
        f"perf regression: {elapsed:.2f}s vs baseline {baseline:.2f}s "
        f"(limit {limit:.2f}s = 1.5x)"
    )
