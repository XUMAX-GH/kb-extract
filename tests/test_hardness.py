import pytest

from kb_extract.contracts import SectionNode
from kb_extract.errors import HardnessViolation
from kb_extract.hardness import check_h3_anchor_uniqueness, check_h4_anchor_completeness


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
