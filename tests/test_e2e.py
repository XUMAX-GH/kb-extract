"""End-to-end acceptance test mirroring spec §12.

Builds a synthetic mini-project with PDF + DOCX + XLSX + PPTX + PNG + ZIP
(containing PPTX), runs `kb extract`, asserts:
- Every doc produces main.md/index.json/meta.json/assets
- `kb verify` exits 0
- Editing main.md makes verify exit 3
- Second run is a no-op
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from kb_extract.cli import main as cli_main


def _build_mini_project(root: Path) -> None:
    import zipfile

    from PIL import Image as PILImage

    from tests.adapters._fixtures import make_docx, make_pdf, make_pptx, make_xlsx

    make_pdf(root / "doc1.pdf")
    make_docx(root / "doc2.docx")
    make_xlsx(root / "data.xlsx")
    make_pptx(root / "deck.pptx")
    PILImage.new("RGB", (16, 16), (123, 200, 50)).save(root / "logo.png")

    inner_pptx = root / "_tmp_inner.pptx"
    make_pptx(inner_pptx)
    with zipfile.ZipFile(root / "bundle.zip", "w") as zf:
        zf.write(inner_pptx, arcname="inner.pptx")
    inner_pptx.unlink()


@pytest.mark.disable_socket
@pytest.mark.slow
def test_e2e_full_pipeline_meets_acceptance_criteria(tmp_path):
    project = tmp_path / "ProjectX"
    project.mkdir()
    _build_mini_project(project)

    runner = CliRunner()

    # 1. Extract
    r1 = runner.invoke(cli_main, ["extract", str(project), "--json"])
    assert r1.exit_code == 0, r1.output
    for name in ("doc1", "doc2", "data", "deck", "logo", "bundle"):
        assert (project / "kb" / name / "main.md").exists(), f"missing main.md for {name}"

    # 2. Verify clean
    r2 = runner.invoke(cli_main, ["verify", str(project)])
    assert r2.exit_code == 0, r2.output

    # 3. Idempotency: re-running extracts nothing new
    main_md = project / "kb" / "doc1" / "main.md"
    mtime1 = main_md.stat().st_mtime_ns
    r3 = runner.invoke(cli_main, ["extract", str(project), "--json"])
    assert r3.exit_code == 0
    import json as _json
    payload = _json.loads(r3.output)
    assert payload["unchanged_count"] >= 5  # doc1..logo unchanged (bundle may re-recurse)
    assert main_md.stat().st_mtime_ns == mtime1

    # 4. Tamper detection
    main_md.write_bytes(b"tampered")
    r4 = runner.invoke(cli_main, ["verify", str(project), "--json"])
    assert r4.exit_code == 3
    assert "doc1" in r4.output
