from pathlib import Path

from kb_extract.contracts import ExtractionMeta
from kb_extract.manifest import Manifest, ManifestRow


def _meta(**kw):
    defaults: dict = dict(
        source_path="P/foo.pdf", source_sha256="a" * 64, source_bytes=10,
        source_mtime_iso="2026-06-09T12:00:00+00:00",
        adapter_name="pdf_docling", adapter_version="abc",
        tool_versions={"docling": "2.0"}, extracted_at_iso="2026-06-09T12:01:00+00:00",
        outline_source="bookmark", status="ok",
    )
    defaults.update(kw)
    return ExtractionMeta(**defaults)


def test_manifest_creates_db_and_table(tmp_path):
    db = tmp_path / "manifest.sqlite"
    m = Manifest(db)
    m.close()
    assert db.exists()


def test_upsert_and_get_returns_row(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.upsert(Path("/abs/P/foo.pdf"), _meta(), output_sha256="b" * 64)
    row = m.get(Path("/abs/P/foo.pdf"))
    assert isinstance(row, ManifestRow)
    assert row.status == "ok"
    assert row.source_sha256 == "a" * 64
    assert row.output_sha256 == "b" * 64
    m.close()


def test_upsert_replaces_existing_row(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.upsert(Path("/abs/P/foo.pdf"), _meta(source_sha256="a" * 64), output_sha256="1" * 64)
    m.upsert(Path("/abs/P/foo.pdf"), _meta(source_sha256="c" * 64), output_sha256="2" * 64)
    row = m.get(Path("/abs/P/foo.pdf"))
    assert row.source_sha256 == "c" * 64
    assert row.output_sha256 == "2" * 64
    m.close()


def test_get_returns_none_for_unknown(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    assert m.get(Path("/abs/missing.pdf")) is None
    m.close()


def test_mark_skipped_records_reason(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.mark_skipped(Path("/abs/P/x.stp"), "no_adapter")
    row = m.get(Path("/abs/P/x.stp"))
    assert row.status == "skipped"
    assert row.skipped_reason == "no_adapter"
    m.close()


def test_mark_failed_records_error_repr(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.mark_failed(Path("/abs/P/x.pdf"), "AdapterError('boom')")
    row = m.get(Path("/abs/P/x.pdf"))
    assert row.status == "failed"
    assert "boom" in row.error_repr
    m.close()


def test_iter_returns_all_rows_sorted_by_source_path(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.upsert(Path("/abs/P/b.pdf"), _meta(source_path="P/b.pdf"), output_sha256="x")
    m.upsert(Path("/abs/P/a.pdf"), _meta(source_path="P/a.pdf"), output_sha256="y")
    rows = list(m.iter())
    assert [r.source_path for r in rows] == ["P/a.pdf", "P/b.pdf"]
    m.close()


def test_atomicity_partial_transaction_does_not_persist(tmp_path):
    """SQLite ACID: if we crash mid-transaction the row should not appear."""
    db = tmp_path / "m.sqlite"
    m = Manifest(db)
    try:
        with m.conn:  # transaction
            m.conn.execute("INSERT INTO sources(source_path, status) VALUES (?, ?)",
                           ("P/x.pdf", "ok"))
            raise RuntimeError("simulated crash")
    except RuntimeError:
        pass
    # Reopen
    m.close()
    m2 = Manifest(db)
    assert m2.get(Path("/abs/P/x.pdf")) is None
    m2.close()
