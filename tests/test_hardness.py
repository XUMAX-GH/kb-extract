import hashlib

import pytest

from kb_extract.contracts import AssetRef, SectionNode
from kb_extract.errors import HardnessViolation
from kb_extract.hardness import (
    check_h3_anchor_uniqueness,
    check_h4_anchor_completeness,
    check_h5_asset_closure,
    check_h6_asset_hash_truth,
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
