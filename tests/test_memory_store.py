"""sp5 测试：MemoryStore CRUD + 并发安全 + 默认路径。"""

from __future__ import annotations

from pathlib import Path

import pytest

from kb_extract.memory import MemoryStore, default_memory_path

pytestmark = pytest.mark.disable_socket


def test_default_path_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KB_EXTRACT_HOME", str(tmp_path))
    assert default_memory_path() == tmp_path / "memory.db"


def test_default_path_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KB_EXTRACT_HOME", raising=False)
    p = default_memory_path()
    assert p.name == "memory.db"
    assert p.parent.name == ".kb-extract"


def test_set_and_get_pref(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    with MemoryStore(db) as m:
        m.set_pref("default.provider", "mock")
        assert m.get_pref("default.provider") == "mock"
        assert m.get_pref("missing") is None


def test_pref_upsert_overwrites(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    with MemoryStore(db) as m:
        m.set_pref("seed", "0")
        m.set_pref("seed", "42")
        assert m.get_pref("seed") == "42"


def test_list_prefs_sorted(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    with MemoryStore(db) as m:
        m.set_pref("z", "1")
        m.set_pref("a", "2")
        keys = list(m.list_prefs().keys())
    assert keys == ["a", "z"]


def test_forget_pref(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    with MemoryStore(db) as m:
        m.set_pref("k", "v")
        assert m.forget_pref("k") is True
        assert m.get_pref("k") is None
        assert m.forget_pref("nope") is False


def test_record_and_recall_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    with MemoryStore(db) as m:
        m.record(project_root="/a", command="extract", args={"force": True}, exit_code=0,
                 summary="ok=1")
        m.record(project_root="/a", command="wiki build", args={"seed": 0}, exit_code=0,
                 summary="topics=2")
        m.record(project_root="/b", command="extract", args={}, exit_code=1, summary="failed")
        out = m.recall(limit=10)
    assert len(out) == 3
    # 最近一条排在前面
    assert out[0].command == "extract"
    assert out[0].project_root == "/b"


def test_recall_filters(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    with MemoryStore(db) as m:
        m.record(project_root="/a", command="extract", args={}, exit_code=0)
        m.record(project_root="/b", command="extract", args={}, exit_code=0)
        m.record(project_root="/a", command="wiki build", args={}, exit_code=0)
        out = m.recall(project_root="/a")
        assert len(out) == 2
        out2 = m.recall(command="wiki build")
        assert len(out2) == 1


def test_h20_concurrent_writes_do_not_corrupt(tmp_path: Path) -> None:
    """H20: 5 个并发线程各写一条，最终 row count == 5。"""
    import threading

    db = tmp_path / "m.db"
    # 先把 schema 建好（避免每个线程重复 CREATE TABLE 竞争）
    with MemoryStore(db):
        pass

    def worker(i: int) -> None:
        with MemoryStore(db) as m:
            m.record(project_root=f"/p{i}", command="extract", args={"i": i}, exit_code=0)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with MemoryStore(db) as m:
        out = m.recall(limit=10)
    assert len(out) == 5


def test_creates_parent_dir_if_missing(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "m.db"
    with MemoryStore(nested) as m:
        m.set_pref("x", "y")
    assert nested.exists()


def test_history_record_returns_id(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    with MemoryStore(db) as m:
        rid1 = m.record(project_root="/x", command="extract", args={}, exit_code=0)
        rid2 = m.record(project_root="/x", command="extract", args={}, exit_code=0)
    assert isinstance(rid1, int) and rid1 >= 1
    assert rid2 > rid1
