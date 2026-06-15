"""Tests for H21 v2 schema invariants (PR-A)."""
from __future__ import annotations

import pytest

from kb_extract.errors import HardnessViolation
from kb_extract.wiki.taxonomy import (
    CategoryNode,
    TaxonomyConfigV2,
    validate_taxonomy_v2,
)

pytestmark = pytest.mark.disable_socket


def _node(slug: str, layer: str, children=()) -> CategoryNode:
    return CategoryNode(slug=slug, title=slug.upper(), layer=layer,
                       children=tuple(children))


def test_valid_4_layer_tree_passes() -> None:
    cfg = TaxonomyConfigV2(
        version=2, source_prd="prd", source_pes_glob=None,
        categories=(_node("a", "system", [
            _node("b", "subsystem", [
                _node("c", "part", [
                    _node("d", "function")
                ])
            ])
        ]),),
    )
    validate_taxonomy_v2(cfg)  # no raise


def test_rejects_unknown_layer() -> None:
    cfg = TaxonomyConfigV2(
        version=2, source_prd="prd", source_pes_glob=None,
        categories=(_node("a", "bogus"),),
    )
    with pytest.raises(HardnessViolation) as excinfo:
        validate_taxonomy_v2(cfg)
    assert excinfo.value.invariant == "H21"
    assert "layer" in excinfo.value.detail.lower()


def test_rejects_depth_greater_than_4() -> None:
    cfg = TaxonomyConfigV2(
        version=2, source_prd="prd", source_pes_glob=None,
        categories=(_node("a", "system", [
            _node("b", "subsystem", [
                _node("c", "part", [
                    _node("d", "function", [
                        _node("e", "function")  # depth 5
                    ])
                ])
            ])
        ]),),
    )
    with pytest.raises(HardnessViolation) as excinfo:
        validate_taxonomy_v2(cfg)
    assert excinfo.value.invariant == "H21"


def test_rejects_layer_not_descending() -> None:
    # subsystem child under part parent (jumps back up)
    cfg = TaxonomyConfigV2(
        version=2, source_prd="prd", source_pes_glob=None,
        categories=(_node("a", "part", [
            _node("b", "subsystem"),
        ]),),
    )
    with pytest.raises(HardnessViolation) as excinfo:
        validate_taxonomy_v2(cfg)
    assert excinfo.value.invariant == "H21"


def test_rejects_layer_skip() -> None:
    # system -> part (skipping subsystem)
    cfg = TaxonomyConfigV2(
        version=2, source_prd="prd", source_pes_glob=None,
        categories=(_node("a", "system", [
            _node("b", "part"),
        ]),),
    )
    with pytest.raises(HardnessViolation) as excinfo:
        validate_taxonomy_v2(cfg)
    assert excinfo.value.invariant == "H21"


def test_rejects_duplicate_sibling_slugs() -> None:
    cfg = TaxonomyConfigV2(
        version=2, source_prd="prd", source_pes_glob=None,
        categories=(_node("a", "system", [
            _node("dup", "subsystem"),
            _node("dup", "subsystem"),
        ]),),
    )
    with pytest.raises(HardnessViolation) as excinfo:
        validate_taxonomy_v2(cfg)
    assert excinfo.value.invariant == "H21"
    assert "dup" in excinfo.value.detail


def test_same_slug_under_different_parents_is_allowed() -> None:
    # "tweeter" under both Audio/Speaker and Notification/Speaker is OK.
    cfg = TaxonomyConfigV2(
        version=2, source_prd="prd", source_pes_glob=None,
        categories=(
            _node("audio", "system", [
                _node("speaker", "subsystem", [
                    _node("tweeter", "part"),
                ]),
            ]),
            _node("notification", "system", [
                _node("speaker", "subsystem", [
                    _node("tweeter", "part"),
                ]),
            ]),
        ),
    )
    validate_taxonomy_v2(cfg)  # no raise


def test_rejects_empty_slug() -> None:
    cfg = TaxonomyConfigV2(
        version=2, source_prd="prd", source_pes_glob=None,
        categories=(_node("", "system"),),
    )
    with pytest.raises(HardnessViolation) as excinfo:
        validate_taxonomy_v2(cfg)
    assert excinfo.value.invariant == "H21"


def test_rejects_wrong_version() -> None:
    cfg = TaxonomyConfigV2(
        version=1, source_prd="prd", source_pes_glob=None,
        categories=(_node("a", "system"),),
    )
    with pytest.raises(HardnessViolation):
        validate_taxonomy_v2(cfg)
