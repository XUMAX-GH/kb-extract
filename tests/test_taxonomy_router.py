"""route_evidence 4-layer priority tests."""
from __future__ import annotations

import json
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

from kb_extract.wiki import taxonomy
from kb_extract.wiki.taxonomy import (
    Category,
    TaxonomyConfig,
    build_prd_section_map,
    route_evidence,
)
from kb_extract.wiki.topics import EvidenceRef

pytestmark = pytest.mark.disable_socket

_CFG = TaxonomyConfig(
    version=1,
    source_prd="BC PRD",
    categories=(
        Category(
            slug="mechanical",
            title="Mechanical",
            prd_headings=("Mechanical",),
            linked_specs=("M9000010*",),
            keywords=("hinge", "bounce", "stiffness"),
        ),
        Category(
            slug="electrical",
            title="Electrical",
            prd_headings=("Electrical",),
            linked_specs=("M9000011*",),
            keywords=("power", "voltage", "current"),
        ),
        Category(
            slug="keyboard",
            title="Keyboard",
            prd_headings=("Keyset",),
            linked_specs=("M9000015*",),
            keywords=("key", "layout", "keycap"),
        ),
    ),
)

_CFG_WITH_MULTIWORD = TaxonomyConfig(
    version=1,
    source_prd="BC PRD",
    categories=(
        Category(
            slug="electrical",
            title="Electrical",
            prd_headings=("Electrical",),
            linked_specs=("M9000011*",),
            keywords=("Power Supply", "Current"),
        ),
    ),
)

_CFG_WITH_PRD_PATTERN = TaxonomyConfig(
    version=1,
    source_prd="BC PRD",
    categories=(
        Category(
            slug="mechanical",
            title="Mechanical",
            prd_headings=("Mechanical",),
            linked_specs=("BC*",),
            keywords=("hinge",),
        ),
    ),
)


def _ev(doc_id: str, anchor: str, title: str = "") -> EvidenceRef:
    return EvidenceRef(
        doc_id=doc_id,
        anchor=anchor,
        section_title=title,
        page_start=1,
        page_end=1,
    )


def test_route_prd_evidence_by_anchor_position() -> None:
    prd_map = {"sec-0010": "mechanical", "sec-0020": "electrical"}
    result = route_evidence(_ev("BC PRD", "sec-0010"), _CFG, prd_map)
    assert result == "mechanical"


def test_route_prd_evidence_by_anchor_electrical() -> None:
    prd_map = {"sec-0010": "mechanical", "sec-0020": "electrical"}
    result = route_evidence(_ev("BC PRD", "sec-0020"), _CFG, prd_map)
    assert result == "electrical"


def test_route_prd_evidence_is_case_normalized() -> None:
    prd_map = {"sec-0099": "mechanical"}
    result = route_evidence(_ev("bc prd", "sec-0099", "banana smoothie"), _CFG, prd_map)
    assert result == "mechanical"


def test_route_prd_evidence_does_not_use_linked_specs() -> None:
    result = route_evidence(_ev("BC PRD", "sec-0999"), _CFG_WITH_PRD_PATTERN, {})
    assert result == "_uncategorized"


def test_route_non_prd_by_linked_specs_glob() -> None:
    result = route_evidence(_ev("M9000010 Rev B", "a1"), _CFG, {})
    assert result == "mechanical"


def test_route_linked_specs_glob_is_explicitly_case_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(taxonomy, "fnmatchcase", fnmatchcase)
    result = route_evidence(_ev("m9000010 rev b", "a1"), _CFG, {})
    assert result == "mechanical"


def test_route_linked_specs_electrical() -> None:
    result = route_evidence(_ev("M9000011 Blade Electrical", "a1"), _CFG, {})
    assert result == "electrical"


def test_route_by_keyword_fallback() -> None:
    result = route_evidence(_ev("unknown-doc", "a1", "hinge design spec"), _CFG, {})
    assert result == "mechanical"


def test_route_by_keyword_electrical() -> None:
    result = route_evidence(_ev("unknown-doc", "a1", "power supply voltage"), _CFG, {})
    assert result == "electrical"


def test_route_by_multiword_keyword_tokens() -> None:
    result = route_evidence(
        _ev("unknown-doc", "a1", "power supply voltage"),
        _CFG_WITH_MULTIWORD,
        {},
    )
    assert result == "electrical"


def test_route_uncategorized_when_nothing_matches() -> None:
    result = route_evidence(_ev("random-doc", "a1", "banana smoothie"), _CFG, {})
    assert result == "_uncategorized"


def test_build_prd_section_map(tmp_path: Path) -> None:
    prd_dir = tmp_path / "kb" / "BC PRD"
    prd_dir.mkdir(parents=True)
    index = {
        "node_id": "root",
        "title": "",
        "anchor": "",
        "level": 0,
        "page_start": 1,
        "page_end": 99,
        "children": [
            {
                "node_id": "ch1",
                "title": "Mechanical",
                "anchor": "sec-0001",
                "level": 1,
                "page_start": 1,
                "page_end": 10,
                "children": [
                    {
                        "node_id": "s1",
                        "title": "Hinge",
                        "anchor": "sec-0002",
                        "level": 2,
                        "page_start": 2,
                        "page_end": 3,
                        "children": [],
                    },
                ],
            },
            {
                "node_id": "ch2",
                "title": "Electrical",
                "anchor": "sec-0010",
                "level": 1,
                "page_start": 11,
                "page_end": 20,
                "children": [
                    {
                        "node_id": "s2",
                        "title": "Power",
                        "anchor": "sec-0011",
                        "level": 2,
                        "page_start": 12,
                        "page_end": 13,
                        "children": [],
                    },
                ],
            },
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    result = build_prd_section_map(tmp_path / "kb", _CFG)
    assert result["sec-0001"] == "mechanical"
    assert result["sec-0002"] == "mechanical"
    assert result["sec-0010"] == "electrical"
    assert result["sec-0011"] == "electrical"


def test_build_prd_section_map_skips_unmatched_headings(tmp_path: Path) -> None:
    prd_dir = tmp_path / "kb" / "BC PRD"
    prd_dir.mkdir(parents=True)
    index = {
        "node_id": "root",
        "title": "",
        "anchor": "",
        "level": 0,
        "page_start": 1,
        "page_end": 99,
        "children": [
            {
                "node_id": "ch1",
                "title": "Appendix",
                "anchor": "sec-0100",
                "level": 1,
                "page_start": 21,
                "page_end": 30,
                "children": [
                    {
                        "node_id": "s1",
                        "title": "Hinge Notes",
                        "anchor": "sec-0101",
                        "level": 2,
                        "page_start": 22,
                        "page_end": 23,
                        "children": [],
                    },
                ],
            },
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    result = build_prd_section_map(tmp_path / "kb", _CFG)
    assert "sec-0100" not in result
    assert "sec-0101" not in result
