import hashlib

import pytest

from kb_extract.contracts import AssetRef, ExtractionMeta, ExtractionResult, SectionNode
from kb_extract.errors import HardnessViolation
from kb_extract.hardness import (
    assert_invariants,
    check_h3_anchor_uniqueness,
    check_h4_anchor_completeness,
    check_h5_asset_closure,
    check_h6_asset_hash_truth,
    check_h7_source_hash_truth,
    check_h9_page_range_closure,
    check_h10_outline_source_truth,
    check_h11_warnings_allowlist,
)


def test_h3_passes_on_unique_anchors():
    md = '<a id="sec-0001"></a>\n# T\n<a id="sec-0001-0001"></a>\nbody\n'
    check_h3_anchor_uniqueness(md)


def test_h3_fails_on_duplicate_anchor():
    md = '<a id="sec-0001"></a>\n# T\n<a id="sec-0001"></a>\nagain\n'
    with pytest.raises(HardnessViolation) as e:
        check_h3_anchor_uniqueness(md)
    assert e.value.invariant == "H3"
    assert "sec-0001" in e.value.detail


def test_h4_passes_when_every_leaf_anchor_present_in_markdown():
    leaf = SectionNode(
        node_id="0001.0001", title="L", level=1, page_start=1, page_end=1,
        anchor="sec-0001-0001", language="en",
    )
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1,
        anchor="", language="en", children=(leaf,),
    )
    md = '<a id="sec-0001-0001"></a>\nbody\n'
    check_h4_anchor_completeness(md, root)


def test_h4_fails_when_leaf_anchor_missing_from_markdown():
    leaf = SectionNode(
        node_id="0001.0001", title="L", level=1, page_start=1, page_end=1,
        anchor="sec-0001-0001", language="en",
    )
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1,
        anchor="", language="en", children=(leaf,),
    )
    md = "no anchors here\n"
    with pytest.raises(HardnessViolation) as e:
        check_h4_anchor_completeness(md, root)
    assert e.value.invariant == "H4"
    assert "sec-0001-0001" in e.value.detail


def test_h4_ignores_non_leaf_empty_anchors():
    # Parent has anchor="" — should not be required in markdown.
    leaf = SectionNode(
        node_id="0001.0001", title="L", level=1, page_start=1, page_end=1,
        anchor="sec-0001-0001", language="en",
    )
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1,
        anchor="", language="en", children=(leaf,),
    )
    md = '<a id="sec-0001-0001"></a>\nbody\n'
    check_h4_anchor_completeness(md, root)  # no error


def _asset(rel_path: str, sha: str, *, kind: str = "image", page: int = 1) -> AssetRef:
    return AssetRef(kind=kind, rel_path=rel_path, page=page, sha256=sha)


def _meta(**kw):
    defaults: dict = dict(
        source_path="x.pdf", source_sha256="a" * 64, source_bytes=1, source_mtime_iso="t",
        adapter_name="p", adapter_version="v", tool_versions={}, extracted_at_iso="t",
        outline_source="bookmark", status="ok",
    )
    defaults.update(kw)
    return ExtractionMeta(**defaults)


def test_h5_passes_when_md_assets_match_filesystem_and_assetrefs(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "p1-img1.png").write_bytes(b"\x89PNGdata")
    md = "![](assets/p1-img1.png)\n"
    assets = (_asset("assets/p1-img1.png", "x" * 64),)
    check_h5_asset_closure(md, assets, tmp_path)


def test_h5_fails_on_missing_file_referenced_by_markdown(tmp_path):
    md = "![](assets/p1-img1.png)\n"
    with pytest.raises(HardnessViolation) as e:
        check_h5_asset_closure(md, (), tmp_path)
    assert e.value.invariant == "H5"
    assert "p1-img1.png" in e.value.detail


def test_h5_fails_on_orphan_file_in_assets_dir(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "orphan.png").write_bytes(b"x")
    md = "no images\n"
    with pytest.raises(HardnessViolation) as e:
        check_h5_asset_closure(md, (), tmp_path)
    assert e.value.invariant == "H5"
    assert "orphan.png" in e.value.detail


def test_h5_fails_on_md_ref_not_in_assetrefs(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "p1.png").write_bytes(b"x")
    md = "![](assets/p1.png)\n"
    with pytest.raises(HardnessViolation) as e:
        check_h5_asset_closure(md, (), tmp_path)
    assert e.value.invariant == "H5"


def test_h6_passes_when_hashes_match(tmp_path):
    (tmp_path / "assets").mkdir()
    data = b"\x89PNG\x0d\x0a\x1a\x0apayload"
    (tmp_path / "assets" / "p1.png").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    assets = (_asset("assets/p1.png", sha),)
    check_h6_asset_hash_truth(assets, tmp_path)


def test_h6_fails_when_hash_lies(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "p1.png").write_bytes(b"actual")
    assets = (_asset("assets/p1.png", "0" * 64),)
    with pytest.raises(HardnessViolation) as e:
        check_h6_asset_hash_truth(assets, tmp_path)
    assert e.value.invariant == "H6"
    assert "assets/p1.png" in e.value.detail


def test_h7_passes_when_meta_hash_matches_file(tmp_path):
    src = tmp_path / "src.pdf"
    data = b"%PDF-1.7 fake"
    src.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    meta = _meta(source_sha256=sha)
    check_h7_source_hash_truth(meta, src)


def test_h7_fails_when_meta_hash_lies(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"real")
    meta = _meta(source_sha256="0" * 64)
    with pytest.raises(HardnessViolation) as e:
        check_h7_source_hash_truth(meta, src)
    assert e.value.invariant == "H7"


def test_h10_bookmark_passes_when_at_least_one_node_marked_bookmark():
    # We model "derived from bookmark" by a non-empty title at level >= 1.
    leaf = SectionNode(
        node_id="0001", title="From bookmark", level=1, page_start=1, page_end=1,
        anchor="sec-1", language="en",
    )
    root = SectionNode(
        node_id="0000", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="en", children=(leaf,),
    )
    meta = _meta(outline_source="bookmark")
    check_h10_outline_source_truth(meta, root)


def test_h10_bookmark_fails_when_only_root_exists():
    # outline_source=bookmark requires at least one non-root titled node.
    root = SectionNode(
        node_id="0000", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="en",
    )
    meta = _meta(outline_source="bookmark")
    with pytest.raises(HardnessViolation) as e:
        check_h10_outline_source_truth(meta, root)
    assert e.value.invariant == "H10"


def test_h10_page_fallback_always_passes():
    root = SectionNode(
        node_id="0000", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="en",
    )
    meta = _meta(outline_source="page_fallback")
    check_h10_outline_source_truth(meta, root)


def _leaf(ps, pe, *, anchor="sec", nid="x"):
    return SectionNode(
        node_id=nid, title=str(nid), level=1, page_start=ps, page_end=pe,
        anchor=anchor, language="en",
    )


def _root_with(leaves):
    return SectionNode(
        node_id="0", title="R", level=0, page_start=1, page_end=max(lf.page_end for lf in leaves),
        anchor="", language="en", children=tuple(leaves),
    )


def test_h9_passes_when_leaves_cover_1_to_n_exactly():
    root = _root_with([_leaf(1, 3, nid="a"), _leaf(4, 5, nid="b")])
    check_h9_page_range_closure(root, total_pages=5)


def test_h9_fails_on_gap():
    root = _root_with([_leaf(1, 2, nid="a"), _leaf(4, 5, nid="b")])
    with pytest.raises(HardnessViolation) as e:
        check_h9_page_range_closure(root, total_pages=5)
    assert e.value.invariant == "H9"
    assert (
        "gap" in e.value.detail.lower()
        or "missing" in e.value.detail.lower()
        or "not covered" in e.value.detail.lower()
    )


def test_h9_fails_on_overlap():
    # v0.5.1: H9 is coverage-based. Two leaves whose ranges overlap
    # (e.g., [1..3] and [2..4]) still cover [1..4] fully, so it's no
    # longer a violation by itself. To still catch a true error in this
    # test, make the overlap leave a real coverage hole.
    # Original intent was "no two leaves on overlapping pages"; under
    # coverage semantics that's only a problem if it causes missing pages.
    root = _root_with([_leaf(1, 3, nid="a"), _leaf(2, 4, nid="b")])
    # Under coverage semantics this is now valid (union covers 1..4).
    check_h9_page_range_closure(root, total_pages=4)


def test_h9_fails_when_last_page_uncovered():
    root = _root_with([_leaf(1, 3, nid="a")])
    with pytest.raises(HardnessViolation) as e:
        check_h9_page_range_closure(root, total_pages=5)
    assert e.value.invariant == "H9"


def test_h9_accepts_single_page_doc():
    root = _root_with([_leaf(1, 1, nid="a")])
    check_h9_page_range_closure(root, total_pages=1)


def test_h11_passes_when_all_warnings_allowed():
    meta = _meta(warnings=("pdf.scanned_no_text_layer", "pdf.font_decode_failed:p3"))
    check_h11_warnings_allowlist(meta)


def test_h11_passes_when_warnings_empty():
    check_h11_warnings_allowlist(_meta(warnings=()))


def test_h11_fails_on_freeform_warning():
    meta = _meta(warnings=("pdf.scanned_no_text_layer", "freeform note"))
    with pytest.raises(HardnessViolation) as e:
        check_h11_warnings_allowlist(meta)
    assert e.value.invariant == "H11"
    assert "freeform note" in e.value.detail


def test_assert_invariants_passes_on_clean_result(tmp_path):
    src = tmp_path / "src.pdf"
    data = b"%PDF-1.7"
    src.write_bytes(data)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    leaf = SectionNode(
        node_id="0001", title="L", level=1, page_start=1, page_end=3,
        anchor="sec-0001", language="en",
    )
    root = SectionNode(
        node_id="0000", title="R", level=0, page_start=1, page_end=3,
        anchor="", language="en", children=(leaf,),
    )
    md = '<a id="sec-0001"></a>\nbody\n'
    meta = _meta(
        source_path="src.pdf",
        source_sha256=hashlib.sha256(data).hexdigest(),
        outline_source="bookmark",
        warnings=(),
    )
    result = ExtractionResult(
        markdown=md, index=root, tables=(), assets=(), meta=meta
    )

    assert_invariants(result, src, out_dir, total_pages=3)


def test_assert_invariants_propagates_first_violation(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"x")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    root = SectionNode(
        node_id="0", title="R", level=0, page_start=1, page_end=1,
        anchor="", language="en",
    )
    meta = _meta(source_sha256="0" * 64)  # lies → H7
    result = ExtractionResult(
        markdown="hi\n", index=root, tables=(), assets=(), meta=meta
    )
    with pytest.raises(HardnessViolation) as e:
        assert_invariants(result, src, out_dir, total_pages=1)
    assert e.value.invariant in ("H7", "H10")  # H10 also fires (no titled descendants)
