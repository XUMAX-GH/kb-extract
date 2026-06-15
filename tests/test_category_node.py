"""Tests for CategoryNode (hierarchical taxonomy v2) — PR-A data model."""
from __future__ import annotations

import pytest

from kb_extract.wiki.taxonomy import CategoryNode

pytestmark = pytest.mark.disable_socket


def test_leaf_round_trip() -> None:
    node = CategoryNode(
        slug="audio",
        title="Audio System",
        layer="system",
        prd_headings=("Audio System",),
        pes_headings=(),
        linked_specs=(),
        keywords=("audio",),
        children=(),
    )
    rt = CategoryNode.from_dict(node.to_dict())
    assert rt == node


def test_nested_round_trip() -> None:
    leaf = CategoryNode(
        slug="tweeter", title="Tweeter", layer="part",
        prd_headings=(), pes_headings=("Speaker / Tweeter",),
        linked_specs=(), keywords=("tweeter",), children=(),
    )
    mid = CategoryNode(
        slug="speaker", title="Speaker", layer="subsystem",
        prd_headings=("Audio System / Speaker",), pes_headings=(),
        linked_specs=("PES-Speaker-*",), keywords=("speaker",),
        children=(leaf,),
    )
    root = CategoryNode(
        slug="audio", title="Audio System", layer="system",
        prd_headings=("Audio System",), pes_headings=(),
        linked_specs=(), keywords=("audio",),
        children=(mid,),
    )
    rt = CategoryNode.from_dict(root.to_dict())
    assert rt == root
    assert rt.children[0].children[0].slug == "tweeter"


def test_to_dict_uses_lists_for_json() -> None:
    node = CategoryNode(
        slug="x", title="X", layer="system",
        prd_headings=("a",), pes_headings=("b",), linked_specs=("c",),
        keywords=("d",), children=(),
    )
    d = node.to_dict()
    for key in ("prd_headings", "pes_headings", "linked_specs", "keywords", "children"):
        assert isinstance(d[key], list), key
    assert d["layer"] == "system"


def test_from_dict_missing_optional_fields_defaults_empty() -> None:
    node = CategoryNode.from_dict({
        "slug": "x", "title": "X", "layer": "system",
    })
    assert node.prd_headings == ()
    assert node.pes_headings == ()
    assert node.linked_specs == ()
    assert node.keywords == ()
    assert node.children == ()


def test_frozen_cannot_mutate() -> None:
    node = CategoryNode(
        slug="x", title="X", layer="system",
        prd_headings=(), pes_headings=(), linked_specs=(),
        keywords=(), children=(),
    )
    with pytest.raises((AttributeError, Exception)):
        node.slug = "y"  # type: ignore[misc]


def test_children_must_be_tuple_of_nodes_in_round_trip() -> None:
    raw = {
        "slug": "a", "title": "A", "layer": "system",
        "children": [{"slug": "b", "title": "B", "layer": "subsystem"}],
    }
    node = CategoryNode.from_dict(raw)
    assert isinstance(node.children, tuple)
    assert isinstance(node.children[0], CategoryNode)
    assert node.children[0].slug == "b"


def test_layer_field_preserved() -> None:
    for layer in ("system", "subsystem", "part", "function"):
        node = CategoryNode(
            slug="x", title="X", layer=layer,  # type: ignore[arg-type]
            prd_headings=(), pes_headings=(), linked_specs=(),
            keywords=(), children=(),
        )
        assert node.to_dict()["layer"] == layer
        assert CategoryNode.from_dict(node.to_dict()).layer == layer


def test_deep_tree_round_trip_4_levels() -> None:
    fn = CategoryNode(
        slug="eq", title="EQ", layer="function",
        prd_headings=(), pes_headings=(), linked_specs=(),
        keywords=(), children=(),
    )
    pt = CategoryNode(
        slug="tw", title="Tw", layer="part",
        prd_headings=(), pes_headings=(), linked_specs=(),
        keywords=(), children=(fn,),
    )
    ss = CategoryNode(
        slug="sp", title="Sp", layer="subsystem",
        prd_headings=(), pes_headings=(), linked_specs=(),
        keywords=(), children=(pt,),
    )
    sy = CategoryNode(
        slug="au", title="Au", layer="system",
        prd_headings=(), pes_headings=(), linked_specs=(),
        keywords=(), children=(ss,),
    )
    rt = CategoryNode.from_dict(sy.to_dict())
    assert rt.children[0].children[0].children[0].slug == "eq"
    assert rt.children[0].children[0].children[0].layer == "function"
