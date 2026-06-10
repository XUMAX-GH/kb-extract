"""Wiki orchestrator —— `kb wiki build` 的实现。

负责：
1. discover_topics
2. 对每个 topic 调 LlmClient + writer
3. 原子写盘到 `<project>/wiki/<slug>.md`
4. 写 `<project>/wiki/index.json`（topic 列表 + provider/seed 元数据）

不会动 `kb/` 下任何文件（H16）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..layout import kb_dir as _kb_dir
from ..layout import wiki_dir as _wiki_dir
from .providers.base import LlmClient
from .providers.mock import get_provider
from .topics import Topic, discover_topics
from .writer import WikiEntry, build_topic_markdown

# 注意：和主 kb_extract 保持一致 — 写盘走 atomic rename
_WIKI_INDEX_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class WikiResult:
    project_root: Path
    topics: tuple[Topic, ...]
    entries: tuple[WikiEntry, ...]
    provider_name: str
    seed: int
    unresolved_total: int

    @property
    def ok(self) -> bool:
        return self.unresolved_total == 0


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="wb", dir=path.parent, delete=False, prefix=".tmp-", suffix=".part"
    ) as tmp:
        tmp.write(data)
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def _load_source_sha256_map(
    project_root: Path,
    output_dir: Path | None = None,
) -> dict[str, str]:
    """Best-effort: from kb/manifest.sqlite, build {doc_id -> source_sha256}.

    H18 evidence_origins relies on this. If manifest is absent or unreadable,
    we return an empty map and downstream code records empty origin list
    (caller decides whether to fail).
    """
    import sqlite3

    db = _kb_dir(project_root, output_dir) / "manifest.sqlite"
    if not db.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            # Conservative: schema may have evolved; only read the columns
            # we strictly need. If schema differs, just return what we got.
            # Real table is ``sources`` (per kb_extract.manifest schema). Try
            # it first, then fall back to ``manifest`` for any legacy db.
            try:
                cur = conn.execute("SELECT source_path, source_sha256 FROM sources")
            except sqlite3.OperationalError:
                cur = conn.execute("SELECT source_path, source_sha256 FROM manifest")
            for src_path, sha in cur.fetchall():
                if not src_path or not sha:
                    continue
                # doc_id is the basename (folder under kb/) created by orchestrator
                doc_id = Path(src_path).stem
                out[doc_id] = sha
        finally:
            conn.close()
    except sqlite3.Error:
        return {}
    return out


def _serialize_index(
    topics: list[Topic],
    entries: list[WikiEntry],
    provider_name: str,
    seed: int,
    source_sha_map: dict[str, str] | None = None,
) -> bytes:
    sha_map = source_sha_map or {}
    obj = {
        "schema_version": _WIKI_INDEX_SCHEMA,
        "provider": provider_name,
        "seed": seed,
        "topics": [
            {
                "slug": t.slug,
                "title": t.title,
                "evidence_count": len(t.evidence),
                "pin_count": e.pin_count,
                "unresolved_pins": list(e.unresolved_pins),
                "evidence_origins": sorted({
                    sha_map[ev.doc_id]
                    for ev in t.evidence
                    if ev.doc_id in sha_map
                }),
                "evidence": [
                    {
                        "doc_id": ev.doc_id,
                        "anchor": ev.anchor,
                        "section_title": ev.section_title,
                        "page_start": ev.page_start,
                        "page_end": ev.page_end,
                    }
                    for ev in t.evidence
                ],
            }
            for t, e in zip(topics, entries, strict=True)
        ],
    }
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def build_wiki(
    project_root: Path,
    *,
    provider: str | LlmClient = "mock",
    seed: int = 0,
    dry_run: bool = False,
    output_dir: Path | None = None,
) -> WikiResult:
    """全量重建 wiki。如果 wiki/ 已存在，先清空旧文件（仅 *.md + index.json）。

    ``output_dir`` (v0.5.0): 当提供时，kb/ 和 wiki/ 位于 ``output_dir``
    下，而非 ``project_root`` 下。
    """
    project_root = Path(project_root).resolve()
    if not _kb_dir(project_root, output_dir).is_dir():
        raise FileNotFoundError(
            f"未在 {_kb_dir(project_root, output_dir)} 找到 kb/ 目录；请先运行 `kb extract` 抽取。"
        )

    llm: LlmClient
    if isinstance(provider, str):
        llm = get_provider(provider, seed=seed)
        provider_name = provider
    else:
        llm = provider
        provider_name = getattr(provider, "name", "custom")

    topics = discover_topics(project_root, output_dir=output_dir)
    entries = [build_topic_markdown(t, llm) for t in topics]

    if dry_run:
        return WikiResult(
            project_root=project_root,
            topics=tuple(topics),
            entries=tuple(entries),
            provider_name=provider_name,
            seed=seed,
            unresolved_total=sum(len(e.unresolved_pins) for e in entries),
        )

    wiki_dir = _wiki_dir(project_root, output_dir)
    wiki_dir.mkdir(parents=True, exist_ok=True)

    # 清掉旧 .md（保留隐藏文件 / 用户手动文件）
    for old in wiki_dir.glob("*.md"):
        old.unlink()
    idx_path = wiki_dir / "index.json"
    if idx_path.exists():
        idx_path.unlink()

    for topic, entry in zip(topics, entries, strict=True):
        out_path = wiki_dir / f"{topic.slug}.md"
        _atomic_write_bytes(out_path, entry.markdown.encode("utf-8"))

    sha_map = _load_source_sha256_map(project_root, output_dir)
    _atomic_write_bytes(
        idx_path,
        _serialize_index(topics, entries, provider_name, seed, sha_map),
    )

    return WikiResult(
        project_root=project_root,
        topics=tuple(topics),
        entries=tuple(entries),
        provider_name=provider_name,
        seed=seed,
        unresolved_total=sum(len(e.unresolved_pins) for e in entries),
    )


def verify_wiki(project_root: Path, output_dir: Path | None = None) -> list[str]:
    """重读 wiki/index.json，校验每个 evidence pin 都指向真实的 kb anchor。

    返回违规字符串列表（空 = 全部通过 = H14 满足）。

    ``output_dir`` (v0.5.0): 当提供时，从 ``output_dir/wiki/`` 读取索引，
    并以 ``output_dir/kb/`` 作为 anchor 解析根。
    """
    project_root = Path(project_root).resolve()
    wiki_root = _wiki_dir(project_root, output_dir)
    kb_root = _kb_dir(project_root, output_dir)
    idx_path = wiki_root / "index.json"
    if not idx_path.is_file():
        return [f"wiki/index.json 不存在于 {wiki_root}"]

    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"wiki/index.json 不是合法 JSON：{e}"]

    violations: list[str] = []
    for topic in idx.get("topics", []):
        slug = topic["slug"]
        md_path = wiki_root / f"{slug}.md"
        if not md_path.is_file():
            violations.append(f"topic {slug}: wiki/{slug}.md 缺失")
            continue
        if topic.get("unresolved_pins"):
            for n in topic["unresolved_pins"]:
                violations.append(f"topic {slug}: evidence pin [^ev-{n}] 越界")
        # 校验 evidence 的 anchor 是否真实存在 (H14) 且唯一 (H17)
        for ev in topic.get("evidence", []):
            anchor_path = kb_root / ev["doc_id"] / "main.md"
            if not anchor_path.is_file():
                violations.append(
                    f"topic {slug}: 引用文件 kb/{ev['doc_id']}/main.md 不存在"
                )
                continue
            content = anchor_path.read_text(encoding="utf-8")
            needle = f'<a id="{ev["anchor"]}">'
            count = content.count(needle)
            if count == 0:
                violations.append(
                    f"topic {slug}: anchor #{ev['anchor']} 在 kb/{ev['doc_id']}/main.md 中找不到 (H14)"
                )
            elif count > 1:
                violations.append(
                    f"topic {slug}: anchor #{ev['anchor']} 在 kb/{ev['doc_id']}/main.md 中出现了 {count} 次（H17 要求唯一）"
                )

        # H18: evidence_origins must enumerate every distinct source sha256
        # behind this topic's evidence. If we can read manifest, cross-check.
        declared_origins = set(topic.get("evidence_origins", []) or [])
        distinct_doc_ids = {ev["doc_id"] for ev in topic.get("evidence", [])}
        # If manifest is present, reconstruct expected origin set:
        expected_origins = {
            sha
            for did, sha in _load_source_sha256_map(project_root, output_dir).items()
            if did in distinct_doc_ids
        }
        if expected_origins and not expected_origins.issubset(declared_origins):
            missing = sorted(expected_origins - declared_origins)
            violations.append(
                f"topic {slug}: evidence_origins 缺少源 sha256: {missing} (H18)"
            )

    return violations
