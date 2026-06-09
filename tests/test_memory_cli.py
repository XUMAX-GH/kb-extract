"""sp5 测试：kb remember / kb forget / kb recall CLI 子命令。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kb_extract.cli import main

pytestmark = pytest.mark.disable_socket


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("KB_EXTRACT_HOME", str(tmp_path))
    return tmp_path


def test_remember_set_then_list(isolated_home: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["remember", "default.provider", "mock"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["remember", "--list", "--json"])
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert out["default.provider"] == "mock"


def test_remember_without_args_lists(isolated_home: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["remember", "a", "1"])
    r = runner.invoke(main, ["remember"])
    assert r.exit_code == 0
    assert "a = 1" in r.output


def test_remember_with_only_key_errors(isolated_home: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["remember", "lonely-key"])
    assert r.exit_code == 2


def test_forget_returns_zero_when_deleted(isolated_home: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["remember", "k", "v"])
    r = runner.invoke(main, ["forget", "k"])
    assert r.exit_code == 0
    assert "forgot" in r.output


def test_forget_returns_nonzero_when_missing(isolated_home: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["forget", "missing-key"])
    assert r.exit_code == 1


def test_recall_empty(isolated_home: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["recall"])
    assert r.exit_code == 0
    assert "no history" in r.output


def test_recall_after_record(isolated_home: Path, tmp_path: Path) -> None:
    from kb_extract.memory import MemoryStore

    with MemoryStore() as m:
        m.record(project_root=str(tmp_path), command="extract",
                 args={"force": True}, exit_code=0, summary="ok=1")
    runner = CliRunner()
    r = runner.invoke(main, ["recall", "--json"])
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert len(out) == 1
    assert out[0]["command"] == "extract"
    assert out[0]["summary"] == "ok=1"


def test_recall_filter_by_command(isolated_home: Path) -> None:
    from kb_extract.memory import MemoryStore

    with MemoryStore() as m:
        m.record(project_root="/x", command="extract", args={}, exit_code=0)
        m.record(project_root="/x", command="wiki build", args={}, exit_code=0)
    runner = CliRunner()
    r = runner.invoke(main, ["recall", "--command", "wiki build", "--json"])
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert len(out) == 1
    assert out[0]["command"] == "wiki build"
