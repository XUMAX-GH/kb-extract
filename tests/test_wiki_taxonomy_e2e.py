"""Wiki taxonomy mode end-to-end tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki import build_wiki
from kb_extract.wiki.orchestrator import verify_wiki
from kb_extract.wiki.taxonomy import Category, TaxonomyConfig, save_taxonomy

pytestmark = pytest.mark.disable_socket


def _scaffold_taxonomy_kb(root: Path) -> TaxonomyConfig:
    """Create a kb/ with PRD + 2 spec docs, plus a taxonomy.json."""
    kb = root / "kb"

    # PRD
    prd_id = "Test PRD"
    prd_dir = kb / prd_id
    prd_dir.mkdir(parents=True)
    prd_main = (
        '<a id="sec-0001"></a>\n## Mechanical\nMechanical content.\n\n'
        '<a id="sec-0001a"></a>\n### Hinge Design\nHinge content.\n\n'
        '<a id="sec-0001b"></a>\n### Bounce Test\nBounce content.\n\n'
        '<a id="sec-0002"></a>\n## Electrical\nElectrical content.\n\n'
        '<a id="sec-0002a"></a>\n### Power Supply\nPower content.\n'
    )
    (prd_dir / "main.md").write_text(prd_main, encoding="utf-8")
    prd_index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 20,
        "children": [
            {"node_id": "ch1", "title": "Mechanical", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 10,
             "children": [
                 {"node_id": "s1a", "title": "Hinge Design", "anchor": "sec-0001a",
                  "level": 2, "page_start": 2, "page_end": 5, "children": []},
                 {"node_id": "s1b", "title": "Bounce Test", "anchor": "sec-0001b",
                  "level": 2, "page_start": 6, "page_end": 8, "children": []},
             ]},
            {"node_id": "ch2", "title": "Electrical", "anchor": "sec-0002",
             "level": 1, "page_start": 11, "page_end": 20,
             "children": [
                 {"node_id": "s2a", "title": "Power Supply", "anchor": "sec-0002a",
                  "level": 2, "page_start": 12, "page_end": 15, "children": []},
             ]},
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(prd_index), encoding="utf-8")

    # Spec doc linked to mechanical
    spec1_id = "M9000010 Interface"
    spec1_dir = kb / spec1_id
    spec1_dir.mkdir(parents=True)
    (spec1_dir / "main.md").write_text(
        '<a id="sec-0001"></a>\n## Connector\nPogo connector spec.\n',
        encoding="utf-8",
    )
    (spec1_dir / "index.json").write_text(json.dumps({
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 5,
        "children": [
            {"node_id": "c1", "title": "Connector Design", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 5, "children": []},
        ],
    }), encoding="utf-8")

    # Taxonomy config
    cfg = TaxonomyConfig(
        version=1,
        source_prd=prd_id,
        categories=(
            Category(slug="mechanical", title="Mechanical",
                     prd_headings=("Mechanical",),
                     linked_specs=("M9000010*",),
                     keywords=("hinge", "bounce", "connector")),
            Category(slug="electrical", title="Electrical",
                     prd_headings=("Electrical",),
                     linked_specs=(),
                     keywords=("power", "voltage")),
        ),
    )
    wiki_dir = root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    save_taxonomy(cfg, wiki_dir / "taxonomy.json")
    return cfg


def test_taxonomy_build_creates_subdirectories(tmp_path: Path) -> None:
    cfg = _scaffold_taxonomy_kb(tmp_path)
    result = build_wiki(tmp_path, provider="mock", seed=0, taxonomy=cfg)
    assert result.ok
    # Check subdirectories exist
    wiki = tmp_path / "wiki"
    assert (wiki / "mechanical").is_dir()
    # Check _index.md exists
    assert (wiki / "mechanical" / "_index.md").is_file()


def test_taxonomy_build_evidence_routed_correctly(tmp_path: Path) -> None:
    cfg = _scaffold_taxonomy_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0, taxonomy=cfg)
    # M9000010 evidence should be in mechanical (linked_specs match)
    idx = json.loads((tmp_path / "wiki" / "index.json").read_text(encoding="utf-8"))
    mech_topics = [t for t in idx["topics"] if t.get("category") == "mechanical"]
    assert len(mech_topics) > 0


def test_taxonomy_build_verify_passes(tmp_path: Path) -> None:
    cfg = _scaffold_taxonomy_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0, taxonomy=cfg)
    violations = verify_wiki(tmp_path)
    assert violations == []


def test_build_without_taxonomy_unchanged(tmp_path: Path) -> None:
    """Without taxonomy param, behavior is flat (backward compat)."""
    _scaffold_taxonomy_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0)
    wiki = tmp_path / "wiki"
    # Should produce flat *.md files, no subdirectories with _index.md
    md_files = list(wiki.glob("*.md"))
    assert len(md_files) > 0


def test_taxonomy_verify_recursive(tmp_path: Path) -> None:
    """verify_wiki should handle wiki/<cat>/<slug>.md (recursive)."""
    cfg = _scaffold_taxonomy_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0, taxonomy=cfg)
    violations = verify_wiki(tmp_path)
    assert violations == []
