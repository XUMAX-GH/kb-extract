import json

from kb_extract import source_md
from kb_extract.redaction import RedactionPolicy, TextRule
from kb_extract.serialization import serialize_source_meta_json
from kb_extract.source_md import strip_images


def test_strip_images_removes_markdown_images_and_counts():
    md = (
        "# Title\n\n"
        "Intro text.\n\n"
        "![company logo](assets/logo.png)\n\n"
        "Body with inline ![x](data:image/png;base64,AAAA) image.\n\n"
        '<img src="banner.png" alt="b"/>\n'
    )
    out, count = strip_images(md)
    assert "logo.png" not in out
    assert "base64" not in out
    assert "<img" not in out
    assert "# Title" in out
    assert "Intro text." in out
    assert count == 3


def _policy():
    return RedactionPolicy(
        enabled=True,
        text_rules=(TextRule(pattern=r"(?i)\b[MH]\d{6,8}\b", replacement="[PN-REDACTED]"),),
        logo_sha256=(), logo_filename_globs=(), logo_alt_globs=(),
        policy_sha256="d" * 64,
    )


def test_convert_one_strips_images_and_redacts(monkeypatch, tmp_path):
    raw = (
        "# Doc M1320001\n\n"
        "Part M1320001 is secret.\n\n"
        "![logo](assets/logo.png)\n"
    )
    monkeypatch.setattr(source_md, "_markitdown_convert", lambda src: raw)
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    text, stats = source_md.convert_one(src, _policy())
    assert "M1320001" not in text
    assert "[PN-REDACTED]" in text
    assert "logo.png" not in text
    assert text.endswith("\n") and "\r" not in text  # normalized
    assert stats.images_stripped == 1
    assert stats.pn_redacted == 2


def test_convert_one_without_policy_keeps_text_strips_images(monkeypatch, tmp_path):
    raw = "# Doc\n\nPart M1320001 stays.\n\n![logo](assets/logo.png)\n"
    monkeypatch.setattr(source_md, "_markitdown_convert", lambda src: raw)
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    text, stats = source_md.convert_one(src, None)
    assert "M1320001" in text  # no policy -> text unchanged
    assert "logo.png" not in text  # images always stripped
    assert stats.pn_redacted == 0
    assert stats.images_stripped == 1


def test_serialize_source_meta_json_sorted_counts_only():
    out = serialize_source_meta_json(
        source_path="sub/doc.docx",
        source_sha256="a" * 64,
        source_bytes=10,
        source_mtime_iso="t",
        markitdown_version="0.0.1",
        source_md_sha256="b" * 64,
        images_stripped=2,
        pn_redacted=3,
        policy_sha256="c" * 64,
        generated_at_iso="t2",
    )
    assert out.endswith("\n")
    d = json.loads(out)
    assert d["images_stripped"] == 2
    assert d["pn_redacted"] == 3
    assert d["policy_sha256"] == "c" * 64
    assert d["source_md_sha256"] == "b" * 64
    assert set(d.keys()) == {
        "generated_at_iso", "images_stripped", "markitdown_version",
        "pn_redacted", "policy_sha256", "source_bytes", "source_md_sha256",
        "source_mtime_iso", "source_path", "source_sha256",
    }
    # keys sorted
    assert out.index("generated_at_iso") < out.index("source_sha256")


def test_serialize_source_meta_json_null_policy():
    out = serialize_source_meta_json(
        source_path="d.docx", source_sha256="a" * 64, source_bytes=1,
        source_mtime_iso="t", markitdown_version="0.0.1",
        source_md_sha256="b" * 64, images_stripped=0, pn_redacted=0,
        policy_sha256=None, generated_at_iso="t2",
    )
    assert json.loads(out)["policy_sha256"] is None
