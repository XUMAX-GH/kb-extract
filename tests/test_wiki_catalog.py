from kb_extract.wiki.catalog import render_index_md, render_log_entry


def test_render_index_md_groups_by_domain_sorted():
    rows = [
        ("software", "Boot Sequence", "software/boot", ["D1"]),
        ("mechanical", "Hinge Torque", "mechanical/hinge", ["D2", "D1"]),
        ("mechanical", "Keyset Force", "mechanical/keyset", ["D3"]),
    ]
    md = render_index_md(rows)
    assert md.startswith("# ")
    # Domains sorted; mechanical before software.
    assert md.index("mechanical") < md.index("software")
    # Each row uses a wikilink.
    assert "[[mechanical/hinge|Hinge Torque]]" in md
    assert "\r" not in md


def test_render_log_entry_uses_injected_date_and_prefix():
    line = render_log_entry(date="2026-06-25", provider="cached",
                            topics=188, pins=245)
    assert line == "## [2026-06-25] build | provider=cached, topics=188, pins=245"
