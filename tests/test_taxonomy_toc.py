"""Tests for PRD Table-of-Contents driven hierarchy (v0.10.0).

Real Microsoft PRDs extract with degraded body headings (section numbers
survive, titles are lost). The clean numbered hierarchy lives only in the
"Contents" page; these tests cover parsing that TOC into a
system -> subsystem -> part -> function tree and routing body anchors back
into it by section number.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.taxonomy import (
    TaxonomyConfigV2,
    build_prd_toc_section_map_v2,
    generate_taxonomy_v2,
    is_toc_taxonomy,
    parse_prd_toc,
    route_evidence_v2,
)
from kb_extract.wiki.topics import EvidenceRef

pytestmark = pytest.mark.disable_socket


# A Contents page mirroring the real degraded format: a bare section-number
# line followed by a TITLE ... dotted leader ... page-number line, with
# running-header / page-number noise interleaved at page breaks.
_TOC_BLOCK = """\
#### Contents

![p3-img1.png](assets/p3-img1.png)
Product Requirement Document
4/9/2024
M9000012 Rev. B
Microsoft Confidential
Page 4 of  69
Contents
2
PRODUCT OVERVIEW .................................................... 11
2.1
SKU MATRIX .......................................................... 13
2.1.1
MODEL NUMBER ........................................................ 14
3
MECHANICAL .......................................................... 15
3.1
INDUSTRIAL DESIGN (ID) .............................................. 15
Product Requirement Document
Page 5 of  69
3.2
MECHANICAL .......................................................... 16
3.2.1
RETRACTABLE HINGE ................................................... 16
3.2.2
FIT BOUNCE .......................................................... 17
"""


def _body_node(title: str, anchor: str, level: int, children=()) -> dict:
    return {
        "node_id": anchor, "title": title, "anchor": anchor, "level": level,
        "page_start": 1, "page_end": 2, "children": list(children),
    }


def _write_toc_prd(kb_root: Path, doc_id: str = "BC PRD Rev B") -> Path:
    """Write a PRD whose body headings are degraded section numbers."""
    prd_dir = kb_root / doc_id
    prd_dir.mkdir(parents=True)
    # Body: H1 system + numeric body headings (the degraded reality).
    index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 50,
        "children": [
            _body_node("BC", "sec-0001", 1, children=[
                _body_node("Contents", "sec-0003", 4),
                _body_node("2", "sec-0005", 2, children=[
                    _body_node("2.1", "sec-0006", 4),
                ]),
                _body_node("3", "sec-0007", 2, children=[
                    _body_node("3.2", "sec-0008", 4),
                ]),
                # A deeper body number with no exact TOC node -> must roll up.
                _body_node("3.2.7", "sec-0099", 4),
                # Pure noise heading -> system root.
                _body_node("TX", "sec-0050", 2),
            ]),
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    main_md = _TOC_BLOCK + '\n<a id="sec-0005"></a>\n## 2\nbody text\n'
    (prd_dir / "main.md").write_text(main_md, encoding="utf-8")
    return prd_dir


# --- parse_prd_toc ---------------------------------------------------------


def test_parse_toc_extracts_ordered_entries():
    entries = parse_prd_toc(_TOC_BLOCK)
    numbers = [e.number for e in entries]
    assert numbers == ["2", "2.1", "2.1.1", "3", "3.1", "3.2", "3.2.1", "3.2.2"]


def test_parse_toc_strips_dotted_leader_and_page():
    entries = {e.number: e.title for e in parse_prd_toc(_TOC_BLOCK)}
    assert entries["2"] == "PRODUCT OVERVIEW"
    assert entries["3.1"] == "INDUSTRIAL DESIGN (ID)"
    assert entries["3.2.1"] == "RETRACTABLE HINGE"


def test_parse_toc_skips_running_header_noise():
    titles = [e.title for e in parse_prd_toc(_TOC_BLOCK)]
    assert "Product Requirement Document" not in titles
    assert "Microsoft Confidential" not in titles


def test_parse_toc_depth_matches_number_components():
    by_num = {e.number: e.depth for e in parse_prd_toc(_TOC_BLOCK)}
    assert by_num["3"] == 1
    assert by_num["3.1"] == 2
    assert by_num["3.2.1"] == 3


# --- generate_taxonomy_v2(from_toc=True) -----------------------------------


def test_generate_from_toc_builds_four_layers(tmp_path: Path):
    _write_toc_prd(tmp_path)
    cfg = generate_taxonomy_v2(
        tmp_path, prd_doc_id="BC PRD Rev B", from_toc=True,
    )
    assert isinstance(cfg, TaxonomyConfigV2)
    assert len(cfg.categories) == 1
    system = cfg.categories[0]
    assert system.layer == "system"
    assert system.slug == "bc"
    sub_slugs = [c.slug for c in system.children]
    assert sub_slugs == ["product-overview", "mechanical"]
    mech = system.children[1]
    assert mech.layer == "subsystem"
    part_slugs = [c.slug for c in mech.children]
    assert part_slugs == ["industrial-design-id", "mechanical"]
    fn_slugs = [c.slug for c in mech.children[1].children]
    assert fn_slugs == ["retractable-hinge", "fit-bounce"]
    assert mech.children[1].children[0].layer == "function"


def test_generate_from_toc_stores_section_number(tmp_path: Path):
    _write_toc_prd(tmp_path)
    cfg = generate_taxonomy_v2(
        tmp_path, prd_doc_id="BC PRD Rev B", from_toc=True,
    )
    mech = cfg.categories[0].children[1]
    assert mech.prd_headings == ("3",)
    assert mech.children[0].prd_headings == ("3.1",)


def test_generate_from_toc_is_deterministic(tmp_path: Path):
    _write_toc_prd(tmp_path)
    a = generate_taxonomy_v2(tmp_path, prd_doc_id="BC PRD Rev B",
                             from_toc=True)
    b = generate_taxonomy_v2(tmp_path, prd_doc_id="BC PRD Rev B",
                             from_toc=True)
    assert a.to_dict() == b.to_dict()


# --- is_toc_taxonomy -------------------------------------------------------


def test_is_toc_taxonomy_detects_numeric_headings(tmp_path: Path):
    _write_toc_prd(tmp_path)
    cfg = generate_taxonomy_v2(tmp_path, prd_doc_id="BC PRD Rev B",
                               from_toc=True)
    assert is_toc_taxonomy(cfg) is True


def test_is_toc_taxonomy_false_for_heading_mode(tmp_path: Path):
    # A PRD whose body headings carry real titles (not degraded numbers):
    # heading-mode keeps titled subsystems, so the detector returns False.
    doc_id = "Audio PRD"
    prd_dir = tmp_path / doc_id
    prd_dir.mkdir(parents=True)
    index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 20,
        "children": [
            _body_node("Audio", "sec-0001", 1, children=[
                _body_node("Speaker", "sec-0002", 2),
                _body_node("Microphone", "sec-0003", 2),
            ]),
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (prd_dir / "main.md").write_text('<a id="sec-0001"></a>\n# Audio\n',
                                     encoding="utf-8")
    cfg = generate_taxonomy_v2(tmp_path, prd_doc_id=doc_id)
    assert is_toc_taxonomy(cfg) is False


# --- build_prd_toc_section_map_v2 + routing --------------------------------


def test_toc_router_maps_body_number_to_deep_path(tmp_path: Path):
    _write_toc_prd(tmp_path)
    cfg = generate_taxonomy_v2(tmp_path, prd_doc_id="BC PRD Rev B",
                               from_toc=True)
    smap = build_prd_toc_section_map_v2(tmp_path, cfg)
    # body "3" -> subsystem; "3.2" -> part
    assert smap["sec-0007"] == ("bc", "mechanical")
    assert smap["sec-0008"] == ("bc", "mechanical", "mechanical")


def test_toc_router_rolls_up_missing_number(tmp_path: Path):
    _write_toc_prd(tmp_path)
    cfg = generate_taxonomy_v2(tmp_path, prd_doc_id="BC PRD Rev B",
                               from_toc=True)
    smap = build_prd_toc_section_map_v2(tmp_path, cfg)
    # body "3.2.7" has no exact TOC node -> rolls up to part "3.2".
    assert smap["sec-0099"] == ("bc", "mechanical", "mechanical")
    # pure noise "TX" -> system root.
    assert smap["sec-0050"] == ("bc",)


def test_route_evidence_v2_uses_toc_map(tmp_path: Path):
    _write_toc_prd(tmp_path)
    cfg = generate_taxonomy_v2(tmp_path, prd_doc_id="BC PRD Rev B",
                               from_toc=True)
    smap = build_prd_toc_section_map_v2(tmp_path, cfg)
    ev = EvidenceRef(
        doc_id="BC PRD Rev B", anchor="sec-0008",
        section_title="3.2", page_start=16, page_end=16,
    )
    path = route_evidence_v2(ev, cfg, smap, {})
    assert path == ("bc", "mechanical", "mechanical")
