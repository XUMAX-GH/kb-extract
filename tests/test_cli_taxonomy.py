"""CLI tests for v0.7.0 taxonomy commands."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kb_extract.cli import main
from kb_extract.wiki.taxonomy import load_taxonomy

pytestmark = pytest.mark.disable_socket


def _make_prd_kb(root: Path) -> None:
    """Create a minimal kb/ with a PRD doc that taxonomy generate can parse."""
    kb = root / "kb" / "Sample PRD"
    kb.mkdir(parents=True)
    (kb / "main.md").write_text(
        '<a id="sec-0001"></a>\n## Mechanical\nM body.\n\n'
        '<a id="sec-0002"></a>\n## Electrical\nE body.\n',
        encoding="utf-8",
    )
    (kb / "index.json").write_text(json.dumps({
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 4,
        "children": [
            {"node_id": "c1", "title": "Mechanical", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 2, "children": []},
            {"node_id": "c2", "title": "Electrical", "anchor": "sec-0002",
             "level": 1, "page_start": 3, "page_end": 4, "children": []},
        ],
    }), encoding="utf-8")


def test_wiki_taxonomy_generate_writes_default_path(tmp_path: Path) -> None:
    _make_prd_kb(tmp_path)
    runner = CliRunner()
    res = runner.invoke(main, ["wiki", "taxonomy", "generate", str(tmp_path)])
    assert res.exit_code == 0, res.output
    out = tmp_path / "wiki" / "taxonomy.json"
    assert out.is_file()
    cfg = load_taxonomy(out)
    slugs = {c.slug for c in cfg.categories}
    assert {"mechanical", "electrical"}.issubset(slugs)


def test_wiki_taxonomy_generate_custom_out(tmp_path: Path) -> None:
    _make_prd_kb(tmp_path)
    runner = CliRunner()
    custom = tmp_path / "my_taxonomy.json"
    res = runner.invoke(main, [
        "wiki", "taxonomy", "generate", str(tmp_path),
        "--out", str(custom),
    ])
    assert res.exit_code == 0, res.output
    assert custom.is_file()


def test_wiki_build_with_taxonomy_creates_subdirs(tmp_path: Path) -> None:
    _make_prd_kb(tmp_path)
    runner = CliRunner()
    # Generate taxonomy first
    res = runner.invoke(main, ["wiki", "taxonomy", "generate", str(tmp_path)])
    assert res.exit_code == 0, res.output
    # Build with --taxonomy
    tax_path = tmp_path / "wiki" / "taxonomy.json"
    res = runner.invoke(main, [
        "wiki", "build", str(tmp_path),
        "--taxonomy", str(tax_path),
        "--provider", "mock", "--seed", "0",
    ])
    assert res.exit_code == 0, res.output
    # Wiki should be in subdirs now
    wiki = tmp_path / "wiki"
    subdirs = [p for p in wiki.iterdir() if p.is_dir()]
    assert subdirs, "expected at least one category subdir"
    # Each category subdir should have _index.md
    assert any((d / "_index.md").is_file() for d in subdirs)


def test_wiki_build_taxonomy_missing_file_errors(tmp_path: Path) -> None:
    _make_prd_kb(tmp_path)
    runner = CliRunner()
    res = runner.invoke(main, [
        "wiki", "build", str(tmp_path),
        "--taxonomy", str(tmp_path / "nonexistent.json"),
    ])
    assert res.exit_code != 0
