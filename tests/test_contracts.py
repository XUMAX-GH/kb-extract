import dataclasses

import pytest

from kb_extract.contracts import AssetRef, ExtractionMeta, ExtractionResult, SectionNode, TableRef


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


def _meta(**overrides) -> ExtractionMeta:
    defaults: dict = dict(
        source_path="BUR-K/foo.pdf",
        source_sha256="c" * 64,
        source_bytes=1234,
        source_mtime_iso="2026-06-09T12:00:00+00:00",
        adapter_name="pdf_docling",
        adapter_version="abc12345",
        tool_versions={"docling": "2.0.0", "pymupdf": "1.24.0"},
        extracted_at_iso="2026-06-09T12:01:00+00:00",
        outline_source="bookmark",
        status="ok",
        warnings=(),
        skipped_reasons=(),
    )
    defaults.update(overrides)
    return ExtractionMeta(**defaults)


def test_extraction_meta_frozen():
    m = _meta()
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.status = "failed"  # type: ignore[misc]


def test_extraction_meta_outline_source_literal_values():
    for src in ("bookmark", "heading_style", "docling_layout", "page_fallback"):
        _meta(outline_source=src)  # constructs without error


def test_extraction_result_carries_all_parts():
    root = SectionNode(
        node_id="0001",
        title="Root",
        level=0,
        page_start=1,
        page_end=1,
        anchor="",
        language="und",
    )
    result = ExtractionResult(
        markdown="<a id=\"sec-0001\"></a>\nhello\n",
        index=root,
        tables=(),
        assets=(),
        meta=_meta(),
    )
    assert result.markdown.startswith("<a id=")
    assert result.meta.adapter_name == "pdf_docling"


def test_content_sha256_is_deterministic_and_changes_with_markdown():
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1, anchor="", language="und"
    )
    r1 = ExtractionResult(markdown="A\n", index=root, tables=(), assets=(), meta=_meta())
    r2 = ExtractionResult(markdown="A\n", index=root, tables=(), assets=(), meta=_meta())
    r3 = ExtractionResult(markdown="B\n", index=root, tables=(), assets=(), meta=_meta())
    assert r1.content_sha256() == r2.content_sha256()
    assert r1.content_sha256() != r3.content_sha256()
    # length sanity
    assert len(r1.content_sha256()) == 64


def test_content_sha256_includes_sorted_asset_hashes():
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1, anchor="", language="und"
    )
    a1 = AssetRef(kind="image", rel_path="assets/a.png", page=1, sha256="1" * 64)
    a2 = AssetRef(kind="image", rel_path="assets/b.png", page=1, sha256="2" * 64)
    r_ab = ExtractionResult(
        markdown="x\n", index=root, tables=(), assets=(a1, a2), meta=_meta()
    )
    r_ba = ExtractionResult(
        markdown="x\n", index=root, tables=(), assets=(a2, a1), meta=_meta()
    )
    # Order of assets tuple must NOT affect content_sha256 — sorted internally.
    assert r_ab.content_sha256() == r_ba.content_sha256()
    # Different asset → different hash.
    a3 = AssetRef(kind="image", rel_path="assets/c.png", page=1, sha256="3" * 64)
    r_diff = ExtractionResult(
        markdown="x\n", index=root, tables=(), assets=(a1, a3), meta=_meta()
    )
    assert r_diff.content_sha256() != r_ab.content_sha256()
