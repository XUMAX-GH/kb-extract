import json
from pathlib import Path

from click.testing import CliRunner

from kb_extract.cli import main


def _setup(tmp_path: Path) -> Path:
    from kb_extract.adapters._noop import NoopAdapter
    from kb_extract.adapters.base import get_default_registry
    # Ensure noop adapter is registered for CLI tests.
    reg = get_default_registry()
    if ".noop" not in {e for a in reg.all() for e in a.extensions}:
        reg.register(NoopAdapter())
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"x")
    return project


def test_kb_extract_exits_0_on_success(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["extract", str(project)])
    assert result.exit_code == 0, result.output
    assert (project / "kb" / "a" / "main.md").exists()


def test_kb_extract_json_output_parsable(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["extract", str(project), "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["ok_count"] == 1
    assert parsed["overall_status"] == "ok"


def test_kb_extract_dry_run_writes_nothing(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["extract", str(project), "--dry-run"])
    assert result.exit_code == 0
    assert not (project / "kb").exists() or not list((project / "kb").rglob("main.md"))


def test_kb_extract_only_flag_filters_by_extension(tmp_path):
    project = _setup(tmp_path)
    (project / "b.unsupported").write_bytes(b"y")
    runner = CliRunner()
    result = runner.invoke(main, ["extract", str(project), "--only", ".noop", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["sources_processed"] == 1


def test_kb_extract_usage_error_returns_2(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["extract"])  # missing path
    assert result.exit_code == 2


def test_kb_verify_exits_0_on_clean_project(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    result = runner.invoke(main, ["verify", str(project)])
    assert result.exit_code == 0, result.output


def test_kb_verify_exits_3_on_tamper(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    (project / "kb" / "a" / "main.md").write_bytes(b"tampered")
    result = runner.invoke(main, ["verify", str(project)])
    assert result.exit_code == 3
    assert "main.md" in result.output or "violation" in result.output.lower()


def test_kb_verify_json_output_lists_violations(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    (project / "kb" / "a" / "main.md").write_bytes(b"x")
    result = runner.invoke(main, ["verify", str(project), "--json"])
    assert result.exit_code == 3
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["violations"]


def test_kb_verify_fail_fast_returns_first_only(tmp_path):
    project = _setup(tmp_path)
    (project / "b.noop").write_bytes(b"y")
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    (project / "kb" / "a" / "main.md").write_bytes(b"x")
    (project / "kb" / "b" / "main.md").write_bytes(b"x")
    result = runner.invoke(main, ["verify", str(project), "--fail-fast", "--json"])
    payload = json.loads(result.output)
    assert len(payload["violations"]) == 1


def test_kb_adapters_lists_registered_names():
    runner = CliRunner()
    result = runner.invoke(main, ["adapters"])
    assert result.exit_code == 0
    for name in ("pdf_docling", "docx", "xlsx", "pptx", "image"):
        assert name in result.output


def test_kb_adapters_json_machine_readable():
    runner = CliRunner()
    result = runner.invoke(main, ["adapters", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = [a["name"] for a in payload]
    assert "docx" in names


def test_kb_manifest_table_default(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    result = runner.invoke(main, ["manifest", str(project)])
    assert result.exit_code == 0
    assert "a.noop" in result.output
    assert "ok" in result.output.lower()


def test_kb_manifest_status_filter(tmp_path):
    project = _setup(tmp_path)
    (project / "weird.unsupported").write_bytes(b"x")
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    result = runner.invoke(main, ["manifest", str(project), "--status", "skipped"])
    assert result.exit_code == 0
    assert "weird.unsupported" in result.output
    assert "a.noop" not in result.output


def test_kb_manifest_format_json(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    result = runner.invoke(main, ["manifest", str(project), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert any(row["source_path"].endswith("a.noop") for row in payload)


def test_kb_version_outputs_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.5.0" in result.output
