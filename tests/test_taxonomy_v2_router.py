"""Tests for route_evidence_v2 (PR-B): longest-prefix routing."""
from __future__ import annotations

import pytest

from kb_extract.wiki.taxonomy import (
    CategoryNode,
    TaxonomyConfigV2,
    route_evidence_v2,
)
from kb_extract.wiki.topics import EvidenceRef

pytestmark = pytest.mark.disable_socket


def _ev(doc_id: str, anchor: str = "a1", section_title: str = "") -> EvidenceRef:
    return EvidenceRef(
        doc_id=doc_id, anchor=anchor, section_title=section_title,
        page_start=1, page_end=1,
    )


_CFG = TaxonomyConfigV2(
    version=2, source_prd="BC PRD", source_pes_glob="M*",
    categories=(
        CategoryNode(
            slug="audio", title="Audio", layer="system",
            prd_headings=("Audio",),
            children=(
                CategoryNode(
                    slug="speaker", title="Speaker", layer="subsystem",
                    prd_headings=("Speaker",),
                    linked_specs=("M9000003*",),
                    children=(
                        CategoryNode(
                            slug="tweeter", title="Tweeter", layer="part",
                            pes_headings=("Tweeter",),
                            children=(
                                CategoryNode(
                                    slug="frequency-response",
                                    title="Frequency Response",
                                    layer="function",
                                    pes_headings=("Frequency Response",),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        CategoryNode(
            slug="electrical", title="Electrical", layer="system",
            prd_headings=("Electrical",),
            keywords=("power", "voltage"),
        ),
    ),
)


def test_returns_tuple_of_slugs() -> None:
    prd_map = {"sec-0001": ("audio",)}
    result = route_evidence_v2(_ev("BC PRD", "sec-0001"),
                               _CFG, prd_map, {})
    assert result == ("audio",)


def test_prd_section_returns_deepest_path() -> None:
    # PRD H2 anchor mapped to audio/speaker
    prd_map = {"sec-0002": ("audio", "speaker")}
    result = route_evidence_v2(_ev("BC PRD", "sec-0002"),
                               _CFG, prd_map, {})
    assert result == ("audio", "speaker")


def test_pes_section_returns_full_path() -> None:
    # PES anchor mapped to audio/speaker/tweeter/frequency-response
    pes_map = {("M9000003 Speaker PES", "pes-0-0000"):
               ("audio", "speaker", "tweeter", "frequency-response")}
    result = route_evidence_v2(
        _ev("M9000003 Speaker PES", "pes-0-0000"),
        _CFG, {}, pes_map,
    )
    assert result == ("audio", "speaker", "tweeter", "frequency-response")


def test_linked_specs_fallback_when_no_anchor_match() -> None:
    # PES doc, anchor not in pes_map -> falls back to linked_specs (subsystem)
    result = route_evidence_v2(
        _ev("M9000003 Speaker PES", "unknown-anchor"),
        _CFG, {}, {},
    )
    assert result == ("audio", "speaker")


def test_keyword_fallback_to_top_level_system() -> None:
    result = route_evidence_v2(
        _ev("Other Doc", "x", section_title="Power Supply Design"),
        _CFG, {}, {},
    )
    assert result == ("electrical",)


def test_unmatched_returns_uncategorized() -> None:
    result = route_evidence_v2(
        _ev("Other Doc", "x", section_title="random unrelated text"),
        _CFG, {}, {},
    )
    assert result == ("_uncategorized",)


def test_prd_match_takes_priority_over_keyword() -> None:
    """PRD anchor map wins over keyword match even if title hints elsewhere."""
    prd_map = {"sec-0010": ("audio",)}
    # Section title screams "power" (electrical kw) but anchor maps to audio
    result = route_evidence_v2(
        _ev("BC PRD", "sec-0010", section_title="Power Supply"),
        _CFG, prd_map, {},
    )
    assert result == ("audio",)


def test_pes_anchor_match_takes_priority_over_linked_specs() -> None:
    """Deeper PES anchor match (4 layers) beats linked_specs (2 layers)."""
    pes_map = {("M9000003 Speaker PES", "pes-0-0000"):
               ("audio", "speaker", "tweeter")}
    result = route_evidence_v2(
        _ev("M9000003 Speaker PES", "pes-0-0000"),
        _CFG, {}, pes_map,
    )
    assert result == ("audio", "speaker", "tweeter")


def test_path_always_valid_in_tree() -> None:
    """Returned path must correspond to an actual chain in the taxonomy."""
    pes_map = {("M9000003 Speaker PES", "pes-0-0000"):
               ("audio", "speaker", "tweeter", "frequency-response")}
    path = route_evidence_v2(
        _ev("M9000003 Speaker PES", "pes-0-0000"),
        _CFG, {}, pes_map,
    )
    # Walk the tree along the path
    nodes = _CFG.categories
    for slug in path:
        match = next((n for n in nodes if n.slug == slug), None)
        assert match is not None, f"path {path} broken at {slug}"
        nodes = match.children


def test_keyword_fallback_descends_to_deepest_matching_node() -> None:
    """Keyword fallback routes to the deepest node whose keywords overlap."""
    cfg = TaxonomyConfigV2(
        version=2, source_prd="BC PRD", source_pes_glob="M*",
        categories=(
            CategoryNode(
                slug="subsystems", title="Subsystems", layer="system",
                prd_headings=("Subsystems",), keywords=("subsystems",),
                children=(
                    CategoryNode(
                        slug="backlight", title="Backlight", layer="subsystem",
                        prd_headings=("Backlight",), keywords=("backlight",),
                    ),
                ),
            ),
        ),
    )
    result = route_evidence_v2(
        _ev("M2222222 Backlight Spec", "a1",
            section_title="Backlight Brightness Uniformity"),
        cfg, {}, {},
    )
    assert result == ("subsystems", "backlight")


def test_doc_title_keyword_fallback_routes_whole_spec_doc() -> None:
    """When section_title has no signal, the doc title routes the evidence."""
    cfg = TaxonomyConfigV2(
        version=2, source_prd="BC PRD", source_pes_glob="M*",
        categories=(
            CategoryNode(
                slug="subsystems", title="Subsystems", layer="system",
                prd_headings=("Subsystems",), keywords=("subsystems",),
                children=(
                    CategoryNode(
                        slug="backlight", title="Backlight", layer="subsystem",
                        prd_headings=("Backlight",), keywords=("backlight",),
                    ),
                ),
            ),
        ),
    )
    # section_title is a bare degraded number -> no overlap; doc title wins
    result = route_evidence_v2(
        _ev("M9000006 Keyset Backlight LED Test", "a1", section_title="3.2"),
        cfg, {}, {},
    )
    assert result == ("subsystems", "backlight")


def test_section_title_keyword_beats_doc_title_keyword() -> None:
    """A specific section title outranks the broader doc title."""
    cfg = TaxonomyConfigV2(
        version=2, source_prd="BC PRD", source_pes_glob="M*",
        categories=(
            CategoryNode(
                slug="subsystems", title="Subsystems", layer="system",
                keywords=("subsystems",),
                children=(
                    CategoryNode(
                        slug="backlight", title="Backlight", layer="subsystem",
                        keywords=("backlight",),
                    ),
                    CategoryNode(
                        slug="touchpad", title="Touchpad", layer="subsystem",
                        keywords=("touchpad",),
                    ),
                ),
            ),
        ),
    )
    result = route_evidence_v2(
        _ev("Backlight Spec", "a1", section_title="Touchpad Force"),
        cfg, {}, {},
    )
    assert result == ("subsystems", "touchpad")
