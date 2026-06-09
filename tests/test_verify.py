from kb_extract.adapters._noop import NoopAdapter
from kb_extract.adapters.base import Registry
from kb_extract.orchestrator import run
from kb_extract.verify import VerifyReport, verify_project


def test_verify_passes_on_freshly_extracted_project(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"x")
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    report = verify_project(project)
    assert isinstance(report, VerifyReport)
    assert report.ok
    assert report.violations == []


def test_verify_detects_edited_main_md(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"x")
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    main_md = project / "kb" / "a" / "main.md"
    main_md.write_bytes(main_md.read_bytes() + b" tampered ")
    report = verify_project(project)
    assert not report.ok
    assert any("a/main.md" in v or "main.md" in v for v in report.violations)


def test_verify_fail_fast_stops_at_first(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"x")
    (project / "b.noop").write_bytes(b"y")
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    # Tamper both
    (project / "kb" / "a" / "main.md").write_bytes(b"bad")
    (project / "kb" / "b" / "main.md").write_bytes(b"bad")
    report = verify_project(project, fail_fast=True)
    assert not report.ok
    assert len(report.violations) == 1
