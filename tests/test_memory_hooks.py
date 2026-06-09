"""sp5 测试：kb extract / verify / wiki 子命令真的会写 history。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kb_extract.cli import main
from kb_extract.memory import MemoryStore

pytestmark = pytest.mark.disable_socket


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """让 KB_EXTRACT_HOME 指向 tmp，避免污染真实用户目录。"""
    home = tmp_path / "kb-home"
    home.mkdir()
    monkeypatch.setenv("KB_EXTRACT_HOME", str(home))
    return home


def _scaffold_kb(root: Path) -> None:
    kb = root / "kb" / "doc1"
    kb.mkdir(parents=True)
    (kb / "main.md").write_text('<a id="a1"></a>\n## section\n正文\n', encoding="utf-8")
    (kb / "index.json").write_text(
        json.dumps({
            "node_id": "root", "title": "", "anchor": "",
            "page_start": 1, "page_end": 10, "level": 0,
            "children": [{
                "node_id": "a1", "title": "section", "anchor": "a1",
                "page_start": 1, "page_end": 1, "level": 1, "children": [],
            }],
        }),
        encoding="utf-8",
    )


def test_wiki_build_records_history(isolated_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _scaffold_kb(project)
    runner = CliRunner()
    r = runner.invoke(main, ["wiki", "build", str(project), "--provider", "mock", "--seed", "0"])
    assert r.exit_code == 0, r.output

    with MemoryStore() as m:
        records = m.recall(limit=5)
    assert any(rec.command == "wiki build" for rec in records)
    rec = next(rec for rec in records if rec.command == "wiki build")
    assert json.loads(rec.args_json) == {"provider": "mock", "seed": 0, "dry_run": False}


def test_wiki_verify_records_history(isolated_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _scaffold_kb(project)
    runner = CliRunner()
    runner.invoke(main, ["wiki", "build", str(project), "--provider", "mock", "--seed", "0"])
    r = runner.invoke(main, ["wiki", "verify", str(project)])
    assert r.exit_code == 0, r.output

    with MemoryStore() as m:
        records = m.recall(command="wiki verify", limit=5)
    assert len(records) >= 1
    assert records[0].exit_code == 0


def test_memory_write_failure_does_not_crash_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """如果 memory 写失败（如磁盘只读），命令本身也不能挂。"""
    # 把 HOME 指向一个不可写的位置（用一个文件路径假装是目录会让 mkdir 失败）
    fake_home = tmp_path / "occupied"
    fake_home.write_text("not a directory")
    monkeypatch.setenv("KB_EXTRACT_HOME", str(fake_home))

    project = tmp_path / "proj"
    project.mkdir()
    _scaffold_kb(project)
    runner = CliRunner()
    # 这一次 memory 应该静默失败但 wiki build 必须成功
    r = runner.invoke(main, ["wiki", "build", str(project), "--provider", "mock", "--seed", "0"])
    assert r.exit_code == 0, r.output
