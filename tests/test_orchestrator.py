from pathlib import Path

from kb_extract.adapters._noop import NoopAdapter
from kb_extract.adapters.base import Registry
from kb_extract.orchestrator import RunReport, run


def _setup_project(tmp_path: Path) -> Path:
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"hello")
    (project / "b.noop").write_bytes(b"world")
    (project / "unknown.xyz").write_bytes(b"?")
    return project


def test_run_extracts_each_known_source(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    report = run(project, registry=reg)
    assert isinstance(report, RunReport)
    assert report.ok_count == 2
    assert report.skipped_count == 1
    assert (project / "kb" / "a" / "main.md").exists()
    assert (project / "kb" / "b" / "main.md").exists()
    assert (project / "kb" / "manifest.sqlite").exists()


def test_run_is_idempotent_on_second_call_no_force(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    main_md = project / "kb" / "a" / "main.md"
    mtime1 = main_md.stat().st_mtime_ns
    report2 = run(project, registry=reg)
    assert report2.ok_count == 0  # nothing re-extracted
    assert report2.unchanged_count == 2
    assert main_md.stat().st_mtime_ns == mtime1


def test_run_force_re_extracts(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    report = run(project, registry=reg, force=True)
    assert report.ok_count == 2


def test_run_dry_run_writes_nothing(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    report = run(project, registry=reg, dry_run=True)
    assert not (project / "kb").exists() or not any((project / "kb").rglob("main.md"))
    assert report.dry_run_count == 2


def test_run_marks_unsupported_as_skipped(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    from kb_extract.manifest import Manifest
    m = Manifest(project / "kb" / "manifest.sqlite")
    rows = list(m.iter())
    statuses = {Path(r.source_path).name: r.status for r in rows}
    assert statuses == {"a.noop": "ok", "b.noop": "ok", "unknown.xyz": "skipped"}
    m.close()


def test_run_h12_no_silent_skip(tmp_path):
    """H12: every discovered file gets a manifest row."""
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    from kb_extract.manifest import Manifest
    m = Manifest(project / "kb" / "manifest.sqlite")
    n_rows = len(list(m.iter()))
    m.close()
    # 3 source files in project
    assert n_rows == 3


def test_run_adapter_exception_marks_failed_and_continues(tmp_path, monkeypatch):
    project = _setup_project(tmp_path)
    reg = Registry()
    noop = NoopAdapter()

    def boom(src, out_dir_tmp):
        if src.name == "a.noop":
            raise RuntimeError("simulated adapter crash")
        return NoopAdapter.extract(noop, src, out_dir_tmp)

    monkeypatch.setattr(noop, "extract", boom)
    reg.register(noop)
    report = run(project, registry=reg)
    assert report.failed_count == 1
    assert report.ok_count == 1


def test_run_atomic_no_orphan_tmp_dir_on_failure(tmp_path, monkeypatch):
    project = _setup_project(tmp_path)
    reg = Registry()
    noop = NoopAdapter()

    def boom(src, out_dir_tmp):
        # Write a fake file then crash.
        (out_dir_tmp / "junk").mkdir(parents=True, exist_ok=True)
        (out_dir_tmp / "junk" / "main.md").write_bytes(b"partial")
        raise RuntimeError("crash after partial write")

    monkeypatch.setattr(noop, "extract", boom)
    reg.register(noop)
    run(project, registry=reg)
    tmp_dirs = list((project / "kb").rglob("*.tmp"))
    assert tmp_dirs == [], f"orphan tmp dirs left behind: {tmp_dirs}"
