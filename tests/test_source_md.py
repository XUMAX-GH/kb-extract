import ast
import json
from pathlib import Path as _P

from kb_extract import source_md
from kb_extract import source_md as _sm
from kb_extract.redaction import RedactionPolicy, TextRule
from kb_extract.serialization import serialize_source_meta_json
from kb_extract.source_manifest import SourceManifest, SourceRow
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


def test_source_manifest_upsert_get_and_idempotency(tmp_path):
    db = tmp_path / "kb" / "source.manifest.sqlite"
    m = SourceManifest(db)
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    m.upsert_ok(
        src,
        source_sha256="a" * 64, source_bytes=1, source_mtime_iso="t",
        markitdown_version="0.0.1", source_md_sha256="b" * 64,
        images_stripped=1, pn_redacted=2, policy_sha256="c" * 64,
        generated_at_iso="t2",
    )
    row = m.get(src)
    assert isinstance(row, SourceRow)
    assert row.status == "ok"
    assert row.source_sha256 == "a" * 64
    assert row.policy_sha256 == "c" * 64
    assert row.markitdown_version == "0.0.1"
    m.upsert_ok(
        src,
        source_sha256="d" * 64, source_bytes=2, source_mtime_iso="t3",
        markitdown_version="0.0.2", source_md_sha256="e" * 64,
        images_stripped=3, pn_redacted=4, policy_sha256=None,
        generated_at_iso="t4",
    )
    row = m.get(src)
    assert row.source_sha256 == "d" * 64
    assert row.policy_sha256 is None
    assert row.markitdown_version == "0.0.2"
    count = m.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    assert count == 1
    m.close()
    db = tmp_path / "kb" / "source.manifest.sqlite"
    m = SourceManifest(db)
    src = tmp_path / "bad.docx"
    src.write_bytes(b"x")
    m.mark_failed(src, "boom")
    row = m.get(src)
    assert row.status == "failed"
    assert row.error_repr == "boom"
    m.close()


def _fake_convert_factory(text_by_name):
    def _convert(src):
        return text_by_name[src.name]
    return _convert


def test_run_source_writes_source_md_and_sidecar(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    (project / "redaction.toml").write_text(
        "[redaction]\nenabled = true\n[[redaction.text]]\n"
        "pattern = '(?i)\\b[MH]\\d{6,8}\\b'\nreplacement = \"[PN-REDACTED]\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        _sm, "_markitdown_convert",
        _fake_convert_factory({"a.docx": "# A M1320001\n\n![l](x.png)\nBody.\n"}),
    )
    report = _sm.run_source(project)
    out = project / "kb" / "a"
    sm_text = (out / "source.md").read_text(encoding="utf-8")
    assert "M1320001" not in sm_text
    assert "x.png" not in sm_text
    assert (out / "source.meta.json").exists()
    assert report.ok_count == 1
    assert report.pn_redacted == 1
    assert report.images_stripped == 1


def test_run_source_is_idempotent_second_run_unchanged(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    monkeypatch.setattr(
        _sm, "_markitdown_convert",
        _fake_convert_factory({"a.docx": "# A\n\nBody.\n"}),
    )
    _sm.run_source(project)
    report2 = _sm.run_source(project)
    assert report2.unchanged_count == 1
    assert report2.ok_count == 0


def test_run_source_reprocesses_with_force(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    monkeypatch.setattr(
        _sm, "_markitdown_convert",
        _fake_convert_factory({"a.docx": "# A\n\nBody.\n"}),
    )
    _sm.run_source(project)
    report2 = _sm.run_source(project, force=True)
    assert report2.ok_count == 1
    assert report2.unchanged_count == 0


def test_run_source_one_bad_file_does_not_abort(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    (project / "b.docx").write_bytes(b"bbb")

    def _convert(src):
        if src.name == "b.docx":
            raise RuntimeError("cannot convert")
        return "# A\n\nBody.\n"

    monkeypatch.setattr(_sm, "_markitdown_convert", _convert)
    report = _sm.run_source(project)
    assert report.ok_count == 1
    assert report.failed_count == 1
    assert (project / "kb" / "a" / "source.md").exists()


def test_run_source_deterministic_bytes_two_projects(monkeypatch, tmp_path):
    raw = "# A M1320001\r\n\r\n![l](x.png)\r\nBody.\r\n"  # CRLF to prove normalization
    monkeypatch.setattr(
        _sm, "_markitdown_convert", lambda src: raw,
    )

    def build(name):
        p = tmp_path / name
        p.mkdir()
        (p / "a.docx").write_bytes(b"aaa")
        return p

    p1, p2 = build("P1"), build("P2")
    _sm.run_source(p1)
    _sm.run_source(p2)
    b1 = (p1 / "kb" / "a" / "source.md").read_bytes()
    b2 = (p2 / "kb" / "a" / "source.md").read_bytes()
    assert b1 == b2
    assert b"\r" not in b1


def test_run_source_dry_run_writes_nothing(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    monkeypatch.setattr(
        _sm, "_markitdown_convert", lambda src: "# A\n\nBody.\n",
    )
    report = _sm.run_source(project, dry_run=True)
    assert not (project / "kb" / "a" / "source.md").exists()
    assert report.dry_run_count == 1


def test_markitdown_imported_only_in_source_md():
    src_root = _P("src/kb_extract")
    offenders = []
    for py in src_root.rglob("*.py"):
        if py.name == "source_md.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "markitdown" in alias.name:
                        offenders.append(py.as_posix())
                        break
            elif isinstance(node, ast.ImportFrom) and node.module and "markitdown" in node.module:
                offenders.append(py.as_posix())
                break
    assert offenders == [], f"markitdown imported outside source_md.py: {offenders}"


def test_source_md_imports_no_llm_sdk():
    import kb_extract.source_md as mod
    tree = ast.parse(_P(mod.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                names.add(n.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    forbidden = {"openai", "anthropic", "litellm", "langchain", "transformers"}
    assert not (names & forbidden)
