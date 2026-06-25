from kb_extract.wiki.frontmatter import build_frontmatter, render_frontmatter


def test_build_frontmatter_sorts_and_dedupes_lists():
    fm = build_frontmatter(
        title="Hinge Torque",
        category_path=("bc", "mechanical"),
        slug="hinge-torque",
        doc_ids=["DOC2", "DOC1", "DOC1"],
        extra_tags=["concept/torque"],
    )
    assert fm["domain"] == "bc"
    assert fm["category_path"] == "bc/mechanical"
    assert fm["evidence_sources"] == ["DOC1", "DOC2"]
    assert fm["tags"] == sorted({
        "domain/bc", "path/bc", "path/mechanical", "concept/torque",
    })


def test_render_frontmatter_is_deterministic_yaml_block():
    fm = build_frontmatter(
        title="T", category_path=("bc",), slug="t", doc_ids=["D1"],
    )
    out = render_frontmatter(fm)
    assert out.startswith("---\n")
    assert out.endswith("---\n")
    assert "\r" not in out
    lines = out.splitlines()
    assert lines[1].startswith("title:")
    assert lines[2].startswith("type:")
    assert render_frontmatter(build_frontmatter(
        title="T", category_path=("bc",), slug="t", doc_ids=["D1"])) == out


def test_render_frontmatter_quotes_title_with_special_chars():
    fm = build_frontmatter(title="A: B #1", category_path=("bc",), slug="x",
                           doc_ids=[])
    out = render_frontmatter(fm)
    assert 'title: "A: B #1"' in out
