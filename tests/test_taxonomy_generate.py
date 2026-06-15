"""Auto-generation of taxonomy.json from PRD structure."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.taxonomy import generate_taxonomy

pytestmark = pytest.mark.disable_socket


def _make_prd(kb_root: Path, doc_id: str = "BC PRD") -> Path:
    """Create a minimal PRD with two chapters and a Reference Documents table."""
    prd_dir = kb_root / doc_id
    prd_dir.mkdir(parents=True)

    index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 50,
        "children": [
            {"node_id": "ch1", "title": "Mechanical", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 20,
             "children": [
                 {"node_id": "s1", "title": "Retractable Hinge", "anchor": "sec-0002",
                  "level": 2, "page_start": 2, "page_end": 5, "children": []},
                 {"node_id": "s2", "title": "Flat Bounce", "anchor": "sec-0003",
                  "level": 2, "page_start": 6, "page_end": 10, "children": []},
             ]},
            {"node_id": "ch2", "title": "Electrical", "anchor": "sec-0010",
             "level": 1, "page_start": 21, "page_end": 40,
             "children": [
                 {"node_id": "s3", "title": "Power Draw", "anchor": "sec-0011",
                  "level": 2, "page_start": 22, "page_end": 25, "children": []},
             ]},
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    main_md = (
        '<a id="sec-0001"></a>\n'
        "# Mechanical\n\n"
        "## Reference Documents\n\n"
        "| Document | Number |\n"
        "|---|---|\n"
        "| Keyboard Interface | M9000010 Rev B |\n\n"
        '<a id="sec-0010"></a>\n'
        "# Electrical\n\n"
        "## Reference Documents\n\n"
        "| Document | Number |\n"
        "|---|---|\n"
        "| Blade Electrical | M9000011 |\n"
    )
    (prd_dir / "main.md").write_text(main_md, encoding="utf-8")
    return prd_dir


def test_generate_taxonomy_from_prd(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _make_prd(kb_root)
    cfg = generate_taxonomy(kb_root, prd_doc_id="BC PRD")
    assert cfg.version == 1
    assert cfg.source_prd == "BC PRD"
    slugs = [c.slug for c in cfg.categories]
    assert "mechanical" in slugs
    assert "electrical" in slugs


def test_generate_taxonomy_extracts_linked_specs(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _make_prd(kb_root)
    cfg = generate_taxonomy(kb_root, prd_doc_id="BC PRD")
    mech = next(c for c in cfg.categories if c.slug == "mechanical")
    assert any("M9000010" in s for s in mech.linked_specs)


def test_generate_taxonomy_generates_keywords_from_subheadings(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _make_prd(kb_root)
    cfg = generate_taxonomy(kb_root, prd_doc_id="BC PRD")
    mech = next(c for c in cfg.categories if c.slug == "mechanical")
    kw_lower = {k.lower() for k in mech.keywords}
    assert "hinge" in kw_lower or "retractable" in kw_lower


def test_generate_taxonomy_auto_detects_prd(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _make_prd(kb_root, "My Product PRD 1.0")
    cfg = generate_taxonomy(kb_root)
    assert cfg.source_prd == "My Product PRD 1.0"


def test_generate_taxonomy_raises_when_no_prd(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir(parents=True)
    (kb_root / "some-spec").mkdir()
    (kb_root / "some-spec" / "index.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="PRD"):
        generate_taxonomy(kb_root)
