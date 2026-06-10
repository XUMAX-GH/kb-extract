"""Integration test for --output-dir flag (kb extract / verify / wiki build / wiki verify).

When --output-dir is provided, kb/ and wiki/ artifacts must be written
*under that directory* instead of under the project root. This lets users
keep generated artifacts separate from source files (e.g., source is in a
read-only or write-restricted folder).
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest
from click.testing import CliRunner

from kb_extract.cli import main

pytestmark = pytest.mark.disable_socket


def _make_minimal_pdf(target: Path) -> None:
    doc = fitz.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((72, 100), "Big Heading", fontname="helv", fontsize=22)
    p1.insert_text((72, 150), "Some body content.", fontname="helv", fontsize=10)
    doc.save(str(target))
    doc.close()


@pytest.fixture
def src_proj(tmp_path: Path) -> Path:
    proj = tmp_path / "source-only"
    proj.mkdir()
    _make_minimal_pdf(proj / "doc1.pdf")
    return proj


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    # Intentionally non-existent; the CLI should create it.
    return tmp_path / "elsewhere" / "kb-output"


def test_extract_with_output_dir_writes_kb_under_output_dir(
    src_proj: Path, out_dir: Path,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["extract", "--output-dir", str(out_dir), "--json", str(src_proj)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    # kb/ MUST be under out_dir, NOT under src_proj
    assert not (src_proj / "kb").exists(), (
        f"kb/ leaked into source folder: {src_proj}"
    )
    assert (out_dir / "kb" / "manifest.sqlite").exists()
    assert (out_dir / "kb" / "doc1" / "main.md").exists()


def test_verify_with_output_dir_reads_kb_from_output_dir(
    src_proj: Path, out_dir: Path,
) -> None:
    runner = CliRunner()
    r1 = runner.invoke(
        main, ["extract", "--output-dir", str(out_dir), str(src_proj)],
        catch_exceptions=False,
    )
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(
        main, ["verify", "--output-dir", str(out_dir), "--json", str(src_proj)],
        catch_exceptions=False,
    )
    assert r2.exit_code == 0, r2.output
    payload = json.loads(r2.output)
    assert payload["ok"] is True
    assert payload["violations"] == []


def test_wiki_build_with_output_dir_writes_wiki_under_output_dir(
    src_proj: Path, out_dir: Path,
) -> None:
    runner = CliRunner()
    r1 = runner.invoke(
        main, ["extract", "--output-dir", str(out_dir), str(src_proj)],
        catch_exceptions=False,
    )
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(
        main,
        [
            "wiki", "build",
            "--output-dir", str(out_dir),
            "--provider", "mock", "--seed", "0",
            "--json", str(src_proj),
        ],
        catch_exceptions=False,
    )
    assert r2.exit_code == 0, r2.output
    assert (out_dir / "wiki" / "index.json").exists()
    assert not (src_proj / "wiki").exists()
    # wiki verify also honors --output-dir
    r3 = runner.invoke(
        main, ["wiki", "verify", "--output-dir", str(out_dir), "--json", str(src_proj)],
        catch_exceptions=False,
    )
    assert r3.exit_code == 0, r3.output
    payload = json.loads(r3.output)
    assert payload["ok"] is True


def test_output_dir_creates_missing_intermediate_dirs(
    src_proj: Path, tmp_path: Path,
) -> None:
    nested = tmp_path / "a" / "b" / "c" / "out"  # 4 levels deep, none exist
    runner = CliRunner()
    result = runner.invoke(
        main, ["extract", "--output-dir", str(nested), str(src_proj)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert (nested / "kb" / "manifest.sqlite").exists()
