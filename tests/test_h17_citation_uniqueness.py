"""sp4 测试：H17 anchor 唯一性 + H18 multi-source provenance + H19 stability。

H17 升级了 verify_wiki：原本只查 anchor 存在，现在还要求唯一。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki import build_wiki
from kb_extract.wiki.orchestrator import verify_wiki

pytestmark = pytest.mark.disable_socket


def _scaffold(root: Path, *, duplicate_anchor: bool = False) -> None:
    kb = root / "kb"
    d = kb / "doc1"
    d.mkdir(parents=True)
    main = '<a id="a1"></a>\n## thermal management\n正文1\n\n<a id="a2"></a>\n## thermal materials\n正文2\n'
    if duplicate_anchor:
        # 故意复制一次 a1，制造 H17 违规
        main = main + '\n<a id="a1"></a>\nfake duplicate\n'
    (d / "main.md").write_text(main, encoding="utf-8")
    (d / "index.json").write_text(
        json.dumps({
            "node_id": "root", "title": "", "anchor": "",
            "page_start": 1, "page_end": 10, "level": 0,
            "children": [
                {"node_id": "a1", "title": "thermal management", "anchor": "a1",
                 "page_start": 1, "page_end": 1, "level": 1, "children": []},
                {"node_id": "a2", "title": "thermal materials", "anchor": "a2",
                 "page_start": 2, "page_end": 2, "level": 1, "children": []},
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )


def test_h17_verify_detects_duplicate_anchor(tmp_path: Path) -> None:
    _scaffold(tmp_path, duplicate_anchor=False)
    build_wiki(tmp_path, provider="mock", seed=0)
    # 第一次正常通过
    assert verify_wiki(tmp_path) == []
    # 现在污染 main.md 让 a1 重复
    md = tmp_path / "kb" / "doc1" / "main.md"
    md.write_text(md.read_text(encoding="utf-8") + '\n<a id="a1"></a>\nbad dup\n',
                  encoding="utf-8")
    violations = verify_wiki(tmp_path)
    assert any("H17" in v for v in violations), f"expected H17 hit, got {violations}"


def test_h17_passes_when_anchor_unique(tmp_path: Path) -> None:
    _scaffold(tmp_path, duplicate_anchor=False)
    build_wiki(tmp_path, provider="mock", seed=0)
    assert all("H17" not in v for v in verify_wiki(tmp_path))
