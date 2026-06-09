"""sp3 端到端 + hardness 测试。

H14 evidence-pin-resolves：每个 [^ev-N] 都指向真实 kb anchor
H15 wiki-determinism-under-seed：相同 provider + 相同 seed 跨次运行 byte 一致
H16 no-extract-side-effect：build_wiki 不动 kb/ 任何文件
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki import build_wiki
from kb_extract.wiki.orchestrator import verify_wiki

pytestmark = pytest.mark.disable_socket


def _scaffold_kb(root: Path) -> None:
    """造一个最小可用的 kb/ —— 两份文档、若干 anchor。"""
    kb = root / "kb"
    for doc_id, leaves in [
        ("doc1", [("热管理 thermal design", "a1"), ("热材料 thermal materials", "a2")]),
        ("doc2", [("电源 power supply", "b1"), ("供电余量 power margin", "b2")]),
    ]:
        d = kb / doc_id
        d.mkdir(parents=True, exist_ok=True)
        # 真实 anchor 标记 — verify_wiki 会 grep 这个
        main_md = "\n\n".join(f'<a id="{anchor}"></a>\n## {title}\n正文\n' for title, anchor in leaves)
        (d / "main.md").write_text(main_md, encoding="utf-8")
        index = {
            "node_id": "root", "title": "", "anchor": "",
            "page_start": 1, "page_end": 10, "level": 0,
            "children": [
                {"node_id": anchor, "title": title, "anchor": anchor,
                 "page_start": 1, "page_end": 1, "level": 1, "children": []}
                for title, anchor in leaves
            ],
        }
        (d / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


def test_h14_wiki_verify_passes_for_mock_build(tmp_path: Path) -> None:
    _scaffold_kb(tmp_path)
    result = build_wiki(tmp_path, provider="mock", seed=0)
    assert result.unresolved_total == 0
    assert result.ok
    violations = verify_wiki(tmp_path)
    assert violations == [], f"expected H14 ok but got: {violations}"


def test_h15_wiki_output_is_deterministic_per_seed(tmp_path: Path) -> None:
    _scaffold_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=42)
    bytes_first = {
        p.name: p.read_bytes()
        for p in (tmp_path / "wiki").glob("*")
        if p.is_file()
    }

    # 删了 wiki/ 再重跑
    for p in (tmp_path / "wiki").glob("*"):
        p.unlink()
    build_wiki(tmp_path, provider="mock", seed=42)
    bytes_second = {
        p.name: p.read_bytes()
        for p in (tmp_path / "wiki").glob("*")
        if p.is_file()
    }

    assert bytes_first == bytes_second


def test_h15_different_seed_changes_output(tmp_path: Path) -> None:
    _scaffold_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0)
    bytes_seed0 = {p.name: p.read_bytes() for p in (tmp_path / "wiki").glob("*.md")}
    for p in (tmp_path / "wiki").glob("*"):
        p.unlink()
    build_wiki(tmp_path, provider="mock", seed=1)
    bytes_seed1 = {p.name: p.read_bytes() for p in (tmp_path / "wiki").glob("*.md")}
    # 至少有一个文件内容应该不同
    assert bytes_seed0 != bytes_seed1


def test_h16_build_does_not_touch_kb_dir(tmp_path: Path) -> None:
    _scaffold_kb(tmp_path)
    kb_snapshot = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in (tmp_path / "kb").rglob("*")
        if p.is_file()
    }
    build_wiki(tmp_path, provider="mock", seed=0)
    kb_after = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in (tmp_path / "kb").rglob("*")
        if p.is_file()
    }
    assert kb_snapshot == kb_after, "build_wiki 修改了 kb/ 内的文件，违反 H16"


def test_build_wiki_dry_run_does_not_write_disk(tmp_path: Path) -> None:
    _scaffold_kb(tmp_path)
    result = build_wiki(tmp_path, provider="mock", seed=0, dry_run=True)
    assert not (tmp_path / "wiki").exists() or not any((tmp_path / "wiki").iterdir())
    # 但 result 里应该有内容
    assert len(result.topics) > 0


def test_build_wiki_raises_when_no_kb(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_wiki(tmp_path, provider="mock", seed=0)


def test_verify_wiki_detects_missing_anchor(tmp_path: Path) -> None:
    _scaffold_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0)
    # 故意破坏：删 doc1/main.md 里 a1 的 anchor 标签
    md = tmp_path / "kb" / "doc1" / "main.md"
    md.write_text(md.read_text(encoding="utf-8").replace('<a id="a1">', '<a id="WRONG">'),
                  encoding="utf-8")
    violations = verify_wiki(tmp_path)
    # 应至少抓到一条违规
    assert any("a1" in v for v in violations), f"expected to detect missing anchor, got {violations}"
