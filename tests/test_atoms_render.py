from kb_extract.wiki.atoms.render import render_json, render_markdown
from kb_extract.wiki.atoms.schema import coerce_atom


def _a(**o):
    return coerce_atom(
        {"entity": "hinge", "parameter": "force", "value": "5", "unit": "N", "type": "spec", **o},
        doc_id="D", anchor="sec-0001",
    )


def test_json_reproducible():
    a = _a()
    assert render_json([a]) == render_json([a])


def test_md_has_wikilinks_and_anchor():
    md = render_markdown("D", [_a()])
    assert "[[hinge]]" in md and "[[force]]" in md and "(main.md#sec-0001)" in md


def test_md_marks_pending():
    md = render_markdown(
        "D", [coerce_atom({"entity": "pen", "parameter": "force", "type": "spec"},
                          doc_id="D", anchor="sec-2")]
    )
    assert "[待验证]" in md
