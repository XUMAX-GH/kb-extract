"""Tests for wiki.sections.read_section_body."""

from __future__ import annotations

from pathlib import Path


def test_read_section_body_returns_content_between_anchors(tmp_path: Path) -> None:
    """The body between <a id="sec-0001"></a> and the next <a id="..."></a> is returned."""
    from kb_extract.wiki.sections import read_section_body

    kb_root = tmp_path / "kb"
    doc_dir = kb_root / "mydoc"
    doc_dir.mkdir(parents=True)
    main_md = doc_dir / "main.md"
    main_md.write_text(
        '<!-- gen -->\n'
        '<a id="sec-0001"></a>\n'
        '# Introduction\n\n'
        'This is the intro.\n\n'
        '<a id="sec-0002"></a>\n'
        '# Scope\n\n'
        'The scope content here.\n',
        encoding="utf-8",
    )

    body = read_section_body(kb_root, "mydoc", "sec-0001")
    assert "# Introduction" in body
    assert "This is the intro." in body
    assert "# Scope" not in body, "must not bleed into next section"
    assert "<a id=" not in body, "anchor html stripped"


def test_read_section_body_returns_content_to_eof_for_last_section(tmp_path: Path) -> None:
    """The last section runs to EOF."""
    from kb_extract.wiki.sections import read_section_body

    doc_dir = tmp_path / "kb" / "d"
    doc_dir.mkdir(parents=True)
    (doc_dir / "main.md").write_text(
        '<a id="sec-0001"></a>\n# A\n\nfoo\n\n<a id="sec-0002"></a>\n# B\n\nlast section text\n',
        encoding="utf-8",
    )

    body = read_section_body(tmp_path / "kb", "d", "sec-0002")
    assert "# B" in body
    assert "last section text" in body


def test_read_section_body_returns_empty_for_missing_anchor(tmp_path: Path) -> None:
    from kb_extract.wiki.sections import read_section_body

    doc_dir = tmp_path / "kb" / "d"
    doc_dir.mkdir(parents=True)
    (doc_dir / "main.md").write_text('<a id="sec-0001"></a>\n# Only\n', encoding="utf-8")

    body = read_section_body(tmp_path / "kb", "d", "sec-9999")
    assert body == ""


def test_read_section_body_returns_empty_for_missing_doc(tmp_path: Path) -> None:
    from kb_extract.wiki.sections import read_section_body

    body = read_section_body(tmp_path / "kb", "nonexistent", "sec-0001")
    assert body == ""


def test_read_section_body_caps_at_max_chars(tmp_path: Path) -> None:
    """Body is capped at max_chars to keep prompts manageable."""
    from kb_extract.wiki.sections import read_section_body

    doc_dir = tmp_path / "kb" / "d"
    doc_dir.mkdir(parents=True)
    long = "x" * 5000
    (doc_dir / "main.md").write_text(
        f'<a id="sec-0001"></a>\n# A\n\n{long}\n<a id="sec-0002"></a>\n# B\n',
        encoding="utf-8",
    )

    body = read_section_body(tmp_path / "kb", "d", "sec-0001", max_chars=500)
    assert len(body) <= 500
    assert body.endswith("…") or len(body) == 500


def test_read_section_body_skips_anchor_html_inside_body(tmp_path: Path) -> None:
    """Inline anchors like table anchors (tbl-0001) should NOT terminate section."""
    from kb_extract.wiki.sections import read_section_body

    doc_dir = tmp_path / "kb" / "d"
    doc_dir.mkdir(parents=True)
    (doc_dir / "main.md").write_text(
        '<a id="sec-0001"></a>\n# A\n\n'
        'Intro.\n\n'
        '<a id="tbl-0001"></a>\n'
        '| col |\n|---|\n| val |\n\n'
        'More text.\n\n'
        '<a id="sec-0002"></a>\n# B\n',
        encoding="utf-8",
    )

    body = read_section_body(tmp_path / "kb", "d", "sec-0001")
    # Section content should include the inline table anchor + table
    assert "| col |" in body
    assert "More text." in body
    # But NOT bleed into next sec-NNNN section
    assert "# B" not in body


def test_read_section_body_with_similar_anchor_names(tmp_path: Path) -> None:
    """``text.find`` must not pick up ``sec-0001-suffix`` when asked for ``sec-0001``."""
    from kb_extract.wiki.sections import read_section_body

    doc_dir = tmp_path / "kb" / "d"
    doc_dir.mkdir(parents=True)
    # Put the similarly-named anchor FIRST. If our matcher were sloppy
    # (e.g. just looked for `sec-0001`) it'd start the body too early.
    (doc_dir / "main.md").write_text(
        '<a id="sec-0001-suffix"></a>\n'
        '# Wrong section\n'
        'should NOT appear\n\n'
        '<a id="sec-0001"></a>\n'
        '# Right section\n'
        'should appear\n',
        encoding="utf-8",
    )

    body = read_section_body(tmp_path / "kb", "d", "sec-0001")
    assert "should appear" in body
    assert "should NOT appear" not in body, "exact start-anchor match only"
