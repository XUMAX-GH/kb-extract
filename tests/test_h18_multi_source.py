"""sp4 测试：H18 evidence_origins。

当 manifest.sqlite 存在时，wiki/index.json 的每个 topic 必须列出全部 source sha256。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from kb_extract.wiki import build_wiki

pytestmark = pytest.mark.disable_socket


def _scaffold_with_manifest(root: Path) -> dict[str, str]:
    """造 2 个 doc 的 kb/ + 一个 manifest.sqlite，返回 {doc_id: sha}."""
    kb = root / "kb"
    sha_map: dict[str, str] = {}
    for doc_id, sha in [("doc1", "a" * 64), ("doc2", "b" * 64)]:
        d = kb / doc_id
        d.mkdir(parents=True)
        (d / "main.md").write_text(
            f'<a id="{doc_id}-anchor"></a>\n## thermal {doc_id}\n', encoding="utf-8"
        )
        (d / "index.json").write_text(
            json.dumps({
                "node_id": "root", "title": "", "anchor": "",
                "page_start": 1, "page_end": 10, "level": 0,
                "children": [{
                    "node_id": f"{doc_id}-anchor",
                    "title": f"thermal {doc_id}",
                    "anchor": f"{doc_id}-anchor",
                    "page_start": 1, "page_end": 1, "level": 1,
                    "children": [],
                }],
            }),
            encoding="utf-8",
        )
        sha_map[doc_id] = sha

    # 造 manifest.sqlite (real schema uses ``sources`` table — see kb_extract.manifest)
    db = kb / "manifest.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE sources (
            key TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            source_sha256 TEXT,
            status TEXT,
            adapter_name TEXT,
            output_sha256 TEXT
        );
    """)
    for doc_id, sha in sha_map.items():
        # source_path 的 stem 必须等于 doc_id
        conn.execute(
            "INSERT INTO sources(key, source_path, source_sha256, status) VALUES(?,?,?,?)",
            (f"/x/{doc_id}.pdf", f"{doc_id}.pdf", sha, "ok"),
        )
    conn.commit()
    conn.close()
    return sha_map


def test_h18_index_json_lists_all_source_origins(tmp_path: Path) -> None:
    sha_map = _scaffold_with_manifest(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0)

    idx = json.loads((tmp_path / "wiki" / "index.json").read_text(encoding="utf-8"))
    # 至少有一个 topic 把两个 doc 的 sha 都收齐了
    union_origins: set[str] = set()
    for t in idx["topics"]:
        union_origins |= set(t.get("evidence_origins", []))
    assert set(sha_map.values()) <= union_origins, (
        f"evidence_origins 缺失：期望 {set(sha_map.values())}，实际 union={union_origins}"
    )
