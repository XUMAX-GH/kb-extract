import dataclasses

import pytest

from kb_extract.contracts import AssetRef, SectionNode, TableRef


def test_section_node_is_frozen_and_slotted():
    node = SectionNode(
        node_id="0001",
        title="Chapter 1",
        level=1,
        page_start=1,
        page_end=10,
        anchor="",
        language="en",
        children=(),
    )
    assert dataclasses.is_dataclass(node)
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.title = "mutated"  # type: ignore[misc]
    assert "__slots__" in SectionNode.__dict__


def test_section_node_children_is_tuple_of_section_nodes():
    leaf = SectionNode(
        node_id="0001.0001",
        title="Section 1.1",
        level=2,
        page_start=1,
        page_end=2,
        anchor="sec-0001-0001",
        language="en",
    )
    parent = SectionNode(
        node_id="0001",
        title="Chapter 1",
        level=1,
        page_start=1,
        page_end=10,
        anchor="",
        language="en",
        children=(leaf,),
    )
    assert parent.children == (leaf,)
    assert isinstance(parent.children, tuple)


def test_table_ref_rows_json_is_nested_tuple():
    t = TableRef(
        anchor="tbl-0001",
        page=3,
        rows_json=(("col A", "col B"), ("1", "2")),
        rendered_asset="assets/p3-table1.png",
    )
    assert t.anchor == "tbl-0001"
    assert t.rows_json[0] == ("col A", "col B")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.page = 99  # type: ignore[misc]


def test_table_ref_rendered_asset_optional():
    t = TableRef(anchor="tbl-0002", page=4, rows_json=(("x",),), rendered_asset=None)
    assert t.rendered_asset is None


def test_asset_ref_kind_literal():
    a = AssetRef(
        kind="image",
        rel_path="assets/p3-img1.png",
        page=3,
        sha256="a" * 64,
        width=800,
        height=600,
        alt="figure 1",
    )
    assert a.kind == "image"
    assert a.sha256 == "a" * 64


def test_asset_ref_defaults():
    a = AssetRef(kind="image", rel_path="assets/img.png", page=1, sha256="b" * 64)
    assert a.width is None
    assert a.height is None
    assert a.alt == ""
