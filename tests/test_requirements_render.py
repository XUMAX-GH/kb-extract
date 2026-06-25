from pathlib import Path

from kb_extract.wiki.requirements.models import TestItem
from kb_extract.wiki.requirements.render import (
    render_json,
    render_markdown,
    write_requirements,
)


def _item(**kw):
    base = dict(
        category="Mechanical", function="Force", what="Stiffness >= 5",
        how="Not explicitly defined", sample_size="Not specified",
        source_document="PRD", source_section="3.2", evidence_ref="sec-0001",
    )
    base.update(kw)
    return TestItem(**base)


def test_json_is_canonical_and_lf():
    out = render_json([_item()])
    assert out.endswith("\n")
    assert "\r" not in out
    assert '"EvidenceRef": "sec-0001"' in out


def test_markdown_has_anchor_link():
    md = render_markdown("DOC1", [_item()])
    assert "main.md#sec-0001" in md
    assert "\r" not in md


def test_byte_reproducible(tmp_path: Path):
    items = [_item(evidence_ref="sec-0002"), _item(evidence_ref="sec-0001")]
    items_sorted = sorted(items, key=lambda it: it.sort_key())
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    write_requirements(d1, "DOC1", items_sorted)
    write_requirements(d2, "DOC1", items_sorted)
    assert (d1 / "requirements.json").read_bytes() == (d2 / "requirements.json").read_bytes()
    assert (d1 / "requirements.md").read_bytes() == (d2 / "requirements.md").read_bytes()


def test_empty_items_render():
    md = render_markdown("DOC1", [])
    assert "No requirements" in md


def test_written_files_are_lf_only(tmp_path):
    write_requirements(tmp_path / "d", "DOC1", [_item()])
    assert b"\r" not in (tmp_path / "d" / "requirements.json").read_bytes()
    assert b"\r" not in (tmp_path / "d" / "requirements.md").read_bytes()
