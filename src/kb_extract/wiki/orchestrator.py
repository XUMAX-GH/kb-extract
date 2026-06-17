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
from .taxonomy import (
    TaxonomyConfig,
    TaxonomyConfigV2,
    build_pes_section_map_v2,
    build_prd_section_map,
    build_prd_section_map_v2,
    build_prd_toc_section_map_v2,
    is_toc_taxonomy,
    route_evidence,
    route_evidence_v2,
)
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
    min_evidence: int = 1,
    skip_numeric_titles: bool = False,
    taxonomy: TaxonomyConfig | None = None,
) -> WikiResult:
    """全量重建 wiki。如果 wiki/ 已存在，先清空旧文件（仅 *.md + index.json）。

    ``output_dir`` (v0.5.0): 当提供时，kb/ 和 wiki/ 位于 ``output_dir``
    下，而非 ``project_root`` 下。

    ``min_evidence`` / ``skip_numeric_titles`` (v0.6.0): 转发给
    ``discover_topics``。

    ``taxonomy`` (v0.7.0): 当提供时，evidence 按 4-layer routing 分到
    category 子目录，每个 category 内部再做 Jaccard 聚类。
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

    kb_root = _kb_dir(project_root, output_dir)

    if taxonomy is not None:
        return _build_taxonomy_wiki(
            project_root, taxonomy, llm, provider_name, seed, dry_run,
            output_dir, min_evidence, skip_numeric_titles, kb_root,
        )

    topics = discover_topics(
        project_root,
        output_dir=output_dir,
        min_evidence=min_evidence,
        skip_numeric_titles=skip_numeric_titles,
    )
    entries = [build_topic_markdown(t, llm, kb_root=kb_root) for t in topics]

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
    支持 flat (wiki/*.md) 和 taxonomy (wiki/<cat>/<slug>.md) 两种布局。

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

    is_taxonomy = idx.get("taxonomy_mode", False)
    violations: list[str] = []

    for topic in idx.get("topics", []):
        slug = topic["slug"]
        category = topic.get("category")

        if is_taxonomy and category:
            md_path = wiki_root / category / f"{slug}.md"
            display = f"wiki/{category}/{slug}.md"
        else:
            md_path = wiki_root / f"{slug}.md"
            display = f"wiki/{slug}.md"

        if not md_path.is_file():
            violations.append(f"topic {slug}: {display} 缺失")
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


def _build_taxonomy_wiki(
    project_root: Path,
    taxonomy: TaxonomyConfig,
    llm: LlmClient,
    provider_name: str,
    seed: int,
    dry_run: bool,
    output_dir: Path | None,
    min_evidence: int,
    skip_numeric_titles: bool,
    kb_root: Path,
) -> WikiResult:
    """Internal: taxonomy-mode wiki build."""
    import shutil
    from collections import defaultdict

    from .topics import (
        EvidenceRef,
        _is_numeric_title,
        _jaccard_distance,
        _slugify,
        _tokenize,
        _walk_index,
    )

    # 1. Collect ALL evidence from all docs
    all_evidence: list[EvidenceRef] = []
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        index_file = doc_dir / "index.json"
        if not index_file.is_file():
            continue
        try:
            root = json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        pairs: list[tuple[EvidenceRef, frozenset[str]]] = []
        _walk_index(root, doc_dir.name, pairs)
        all_evidence.extend(ev for ev, _ in pairs)

    # 2. Route evidence into categories
    prd_section_map = build_prd_section_map(kb_root, taxonomy)
    cat_evidence: dict[str, list[EvidenceRef]] = defaultdict(list)
    for ev in all_evidence:
        slug = route_evidence(ev, taxonomy, prd_section_map)
        cat_evidence[slug].append(ev)

    # 3. For each category, do Jaccard sub-clustering then build wiki entries
    all_topics: list[Topic] = []
    all_entries: list[WikiEntry] = []
    all_topic_cats: list[str] = []
    cat_slug_to_title = {c.slug: c.title for c in taxonomy.categories}
    cat_slug_to_title["_uncategorized"] = "Uncategorized"

    for cat_slug in sorted(cat_evidence.keys()):
        evs = cat_evidence[cat_slug]
        if not evs:
            continue

        if skip_numeric_titles:
            evs = [e for e in evs if not _is_numeric_title(e.section_title)]
        if not evs:
            continue

        # Sub-cluster within category using Jaccard on section titles
        tok_list = [(_tokenize(e.section_title), e) for e in evs]
        n = len(tok_list)
        uf_parent = list(range(n))

        def _uf_find(x: int, p: list[int] = uf_parent) -> int:
            while p[x] != x:
                p[x] = p[p[x]]
                x = p[x]
            return x

        def _uf_union(a: int, b: int, p: list[int] = uf_parent) -> None:
            ra, rb = _uf_find(a, p), _uf_find(b, p)
            if ra != rb:
                if ra < rb:
                    p[rb] = ra
                else:
                    p[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                if _jaccard_distance(tok_list[i][0], tok_list[j][0]) <= 0.85:
                    _uf_union(i, j)

        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            clusters[_uf_find(i)].append(i)

        for root_idx in sorted(clusters.keys()):
            members = sorted(clusters[root_idx])
            cluster_evs = tuple(tok_list[m][1] for m in members)
            if len(cluster_evs) < min_evidence:
                continue

            # Pick title from most-common non-stopword
            word_count: dict[str, int] = defaultdict(int)
            for m in members:
                for w in tok_list[m][0]:
                    word_count[w] += 1
            if word_count:
                best = sorted(word_count.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            else:
                best = cluster_evs[0].section_title or f"topic-{root_idx}"

            topic_slug = _slugify(best, f"topic-{root_idx:04d}")
            topic = Topic(slug=topic_slug, title=best, evidence=cluster_evs)
            cat_title = cat_slug_to_title.get(cat_slug, cat_slug)
            entry = build_topic_markdown(
                topic, llm, kb_root=kb_root,
                category_slug=cat_slug, category_title=cat_title,
            )
            all_topics.append(topic)
            all_entries.append(entry)
            all_topic_cats.append(cat_slug)

    if dry_run:
        return WikiResult(
            project_root=project_root,
            topics=tuple(all_topics),
            entries=tuple(all_entries),
            provider_name=provider_name,
            seed=seed,
            unresolved_total=sum(len(e.unresolved_pins) for e in all_entries),
        )

    # 4. Write to disk: wiki/<category>/<topic>.md
    wiki_root = _wiki_dir(project_root, output_dir)
    wiki_root.mkdir(parents=True, exist_ok=True)

    # Clean old files
    for old in wiki_root.glob("*.md"):
        old.unlink()
    for cat_dir in wiki_root.iterdir():
        if cat_dir.is_dir() and cat_dir.name != "__pycache__":
            shutil.rmtree(cat_dir)
    idx_path = wiki_root / "index.json"
    if idx_path.exists():
        idx_path.unlink()

    # Handle slug collisions within categories
    cat_slug_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    final_topics: list[Topic] = []
    final_entries: list[WikiEntry] = []
    final_cats: list[str] = []

    for topic, entry, cat in zip(all_topics, all_entries, all_topic_cats, strict=True):
        cat_slug_counts[cat][topic.slug] += 1
        count = cat_slug_counts[cat][topic.slug]
        if count > 1:
            new_slug = f"{topic.slug}-{count}"
            topic = Topic(slug=new_slug, title=topic.title, evidence=topic.evidence)
        final_topics.append(topic)
        final_entries.append(entry)
        final_cats.append(cat)

    for topic, entry, cat in zip(final_topics, final_entries, final_cats, strict=True):
        cat_dir = wiki_root / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        out_path = cat_dir / f"{topic.slug}.md"
        _atomic_write_bytes(out_path, entry.markdown.encode("utf-8"))

    # Write _index.md for each category
    for cat_slug_key in sorted(set(final_cats)):
        cat_dir = wiki_root / cat_slug_key
        cat_title = cat_slug_to_title.get(cat_slug_key, cat_slug_key)
        cat_topics = [
            (t, e) for t, e, c in zip(final_topics, final_entries, final_cats, strict=True)
            if c == cat_slug_key
        ]
        index_lines = [
            f"# {cat_title}",
            "",
            f"> {taxonomy.source_prd} — {cat_title} 子系统知识库",
            "",
            "## 文章列表",
            "",
        ]
        for t, _ in sorted(cat_topics, key=lambda x: x[0].slug):
            index_lines.append(f"- [{t.slug}]({t.slug}.md) — {t.title}")
        index_lines.append("")
        _atomic_write_bytes(cat_dir / "_index.md", "\n".join(index_lines).encode("utf-8"))

    # Write index.json (with category field)
    sha_map = _load_source_sha256_map(project_root, output_dir)
    _atomic_write_bytes(
        idx_path,
        _serialize_taxonomy_index(
            final_topics, final_entries, final_cats,
            provider_name, seed, sha_map,
        ),
    )

    return WikiResult(
        project_root=project_root,
        topics=tuple(final_topics),
        entries=tuple(final_entries),
        provider_name=provider_name,
        seed=seed,
        unresolved_total=sum(len(e.unresolved_pins) for e in final_entries),
    )


def _serialize_taxonomy_index(
    topics: list[Topic],
    entries: list[WikiEntry],
    categories: list[str],
    provider_name: str,
    seed: int,
    source_sha_map: dict[str, str] | None = None,
) -> bytes:
    sha_map = source_sha_map or {}
    obj = {
        "schema_version": _WIKI_INDEX_SCHEMA,
        "provider": provider_name,
        "seed": seed,
        "taxonomy_mode": True,
        "topics": [
            {
                "slug": t.slug,
                "title": t.title,
                "category": cat,
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
            for t, e, cat in zip(topics, entries, categories, strict=True)
        ],
    }
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


# ---------------------------------------------------------------------------
# v0.9.0 Hierarchical v2 build (PR-C)
# ---------------------------------------------------------------------------


def build_wiki_v2(
    project_root: Path,
    *,
    taxonomy: TaxonomyConfigV2,
    provider: str | LlmClient = "mock",
    seed: int = 0,
    dry_run: bool = False,
    output_dir: Path | None = None,
    min_evidence: int = 1,
    skip_numeric_titles: bool = False,
) -> WikiResult:
    """Hierarchical wiki build (v2). Layout::

        wiki/
          _index.md
          <system>/_index.md
          <system>/<subsystem>/_index.md
          <system>/<subsystem>/<part>/_index.md
          <system>/<subsystem>/<part>/<function>/<topic>.md

    Evidence is routed to the deepest matchable category via
    ``route_evidence_v2`` (longest-prefix). Inside each terminal category,
    topics are Jaccard-clustered the same way ``_build_taxonomy_wiki`` does.
    All evidence under a node lives in that node's directory; deeper
    children are not promoted up.
    """
    import shutil
    from collections import defaultdict

    from .topics import (
        EvidenceRef,
        Topic,
        _is_numeric_title,
        _jaccard_distance,
        _slugify,
        _tokenize,
        _walk_index,
    )

    project_root = Path(project_root).resolve()
    kb_root = _kb_dir(project_root, output_dir)
    if not kb_root.is_dir():
        raise FileNotFoundError(
            f"未在 {kb_root} 找到 kb/ 目录；请先运行 `kb extract`。"
        )

    llm: LlmClient
    if isinstance(provider, str):
        llm = get_provider(provider, seed=seed)
        provider_name = provider
    else:
        llm = provider
        provider_name = getattr(provider, "name", "custom")

    # 1. Collect all evidence
    all_evidence: list[EvidenceRef] = []
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        idx_file = doc_dir / "index.json"
        if not idx_file.is_file():
            continue
        try:
            root = json.loads(idx_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        pairs: list[tuple[EvidenceRef, frozenset[str]]] = []
        _walk_index(root, doc_dir.name, pairs)
        all_evidence.extend(ev for ev, _ in pairs)

    # 2. Build PRD + PES section maps, route each evidence
    if is_toc_taxonomy(taxonomy):
        prd_map = build_prd_toc_section_map_v2(kb_root, taxonomy)
    else:
        prd_map = build_prd_section_map_v2(kb_root, taxonomy)
    pes_map = build_pes_section_map_v2(kb_root, taxonomy)

    path_evidence: dict[tuple[str, ...], list[EvidenceRef]] = defaultdict(list)
    for ev in all_evidence:
        path = route_evidence_v2(ev, taxonomy, prd_map, pes_map)
        path_evidence[path].append(ev)

    # 3. For each path, Jaccard-cluster into topics
    all_topics: list[Topic] = []
    all_entries: list[WikiEntry] = []
    all_paths: list[tuple[str, ...]] = []
    titles_by_path = _collect_titles_by_path(taxonomy)

    for cat_path in sorted(path_evidence.keys()):
        evs = path_evidence[cat_path]
        if skip_numeric_titles:
            evs = [e for e in evs if not _is_numeric_title(e.section_title)]
        if not evs:
            continue

        tok_list = [(_tokenize(e.section_title), e) for e in evs]
        n = len(tok_list)
        uf = list(range(n))

        def _f(x: int, p: list[int] = uf) -> int:
            while p[x] != x:
                p[x] = p[p[x]]
                x = p[x]
            return x

        def _u(a: int, b: int, p: list[int] = uf) -> None:
            ra, rb = _f(a, p), _f(b, p)
            if ra != rb:
                if ra < rb:
                    p[rb] = ra
                else:
                    p[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                if _jaccard_distance(tok_list[i][0], tok_list[j][0]) <= 0.85:
                    _u(i, j)

        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            clusters[_f(i)].append(i)

        cat_title = titles_by_path.get(cat_path, cat_path[-1])
        for root_idx in sorted(clusters.keys()):
            members = sorted(clusters[root_idx])
            cluster_evs = tuple(tok_list[m][1] for m in members)
            if len(cluster_evs) < min_evidence:
                continue
            word_count: dict[str, int] = defaultdict(int)
            for m in members:
                for w in tok_list[m][0]:
                    word_count[w] += 1
            if word_count:
                best = sorted(word_count.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            else:
                best = cluster_evs[0].section_title or f"topic-{root_idx}"
            topic_slug = _slugify(best, f"topic-{root_idx:04d}")
            topic = Topic(slug=topic_slug, title=best, evidence=cluster_evs)
            entry = build_topic_markdown(
                topic, llm, kb_root=kb_root,
                category_path=cat_path,
                category_title=cat_title,
            )
            all_topics.append(topic)
            all_entries.append(entry)
            all_paths.append(cat_path)

    if dry_run:
        return WikiResult(
            project_root=project_root,
            topics=tuple(all_topics),
            entries=tuple(all_entries),
            provider_name=provider_name,
            seed=seed,
            unresolved_total=sum(len(e.unresolved_pins) for e in all_entries),
        )

    # 4. Write files
    wiki_root = _wiki_dir(project_root, output_dir)
    if wiki_root.exists():
        for child in wiki_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            elif child.is_file():
                child.unlink()
    wiki_root.mkdir(parents=True, exist_ok=True)

    # Resolve slug collisions per (path, slug)
    slug_counts: dict[tuple[tuple[str, ...], str], int] = defaultdict(int)
    final_topics: list[Topic] = []
    final_entries: list[WikiEntry] = []
    final_paths: list[tuple[str, ...]] = []
    for topic, entry, cat_path in zip(all_topics, all_entries, all_paths, strict=True):
        slug_counts[(cat_path, topic.slug)] += 1
        c = slug_counts[(cat_path, topic.slug)]
        if c > 1:
            new_slug = f"{topic.slug}-{c}"
            topic = Topic(slug=new_slug, title=topic.title,
                          evidence=topic.evidence)
        final_topics.append(topic)
        final_entries.append(entry)
        final_paths.append(cat_path)

    for topic, entry, cat_path in zip(final_topics, final_entries, final_paths,
                                       strict=True):
        target_dir = wiki_root.joinpath(*cat_path) if cat_path else wiki_root
        target_dir.mkdir(parents=True, exist_ok=True)
        out = target_dir / f"{topic.slug}.md"
        _atomic_write_bytes(out, entry.markdown.encode("utf-8"))

    # 5. Recursive _index.md generation
    _write_v2_indices(wiki_root, taxonomy, final_topics, final_paths,
                      titles_by_path, provider_name)

    # 6. Serialize index.json (taxonomy_mode + v2 paths)
    sha_map = _load_source_sha256_map(project_root, output_dir)
    idx_payload = _serialize_taxonomy_v2_index(
        final_topics, final_entries, final_paths,
        provider_name, seed, sha_map, taxonomy,
    )
    _atomic_write_bytes(wiki_root / "index.json", idx_payload)

    return WikiResult(
        project_root=project_root,
        topics=tuple(final_topics),
        entries=tuple(final_entries),
        provider_name=provider_name,
        seed=seed,
        unresolved_total=sum(len(e.unresolved_pins) for e in final_entries),
    )


def _collect_titles_by_path(
    taxonomy: TaxonomyConfigV2,
) -> dict[tuple[str, ...], str]:
    """Map (slug_path,) -> human title from the taxonomy tree."""
    out: dict[tuple[str, ...], str] = {("_uncategorized",): "Uncategorized"}

    def walk(nodes, prefix: tuple[str, ...]) -> None:
        for n in nodes:
            path = (*prefix, n.slug)
            out[path] = n.title
            walk(n.children, path)

    walk(taxonomy.categories, ())
    return out


def _write_v2_indices(
    wiki_root: Path,
    taxonomy: TaxonomyConfigV2,
    final_topics: list,
    final_paths: list[tuple[str, ...]],
    titles_by_path: dict[tuple[str, ...], str],
    provider_name: str,
) -> None:
    """Write recursive _index.md at every level (root + each taxonomy node).

    Each _index.md lists:
      - child folders (with link to ``<slug>/_index.md``)
      - terminal topics in *this* directory (link to ``<slug>.md``)
    """
    # Build path -> list of (topic_slug, topic_title) for terminal topics
    terminals: dict[tuple[str, ...], list[tuple[str, str]]] = {}
    for topic, path in zip(final_topics, final_paths, strict=True):
        terminals.setdefault(path, []).append((topic.slug, topic.title))

    # Root _index.md (lists top-level systems)
    root_lines = [
        f"# {taxonomy.source_prd} — 知识库",
        "",
        f"> 自动生成 (provider={provider_name}, source_pes_glob={taxonomy.source_pes_glob!r})",
        "",
        "## 系统列表",
        "",
    ]
    for sys_node in taxonomy.categories:
        root_lines.append(f"- [{sys_node.title}]({sys_node.slug}/_index.md)")
    # Also list any uncategorized topics under root
    uncategorized = terminals.get(("_uncategorized",), [])
    if uncategorized:
        root_lines.extend(["", "## Uncategorized", ""])
        for slug, title in sorted(uncategorized):
            root_lines.append(f"- [{title}](_uncategorized/{slug}.md)")
    _atomic_write_bytes(wiki_root / "_index.md",
                        ("\n".join(root_lines) + "\n").encode("utf-8"))

    # Recursive per-node _index.md
    def _write_node(node, prefix: tuple[str, ...]) -> None:
        path = (*prefix, node.slug)
        target_dir = wiki_root.joinpath(*path)
        # Only create the index if the directory is going to exist
        # (i.e. has either children or terminal topics under it).
        has_children = bool(node.children)
        has_terminals = path in terminals
        if not has_children and not has_terminals:
            return
        target_dir.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# {node.title}",
            "",
            f"> Layer: `{node.layer}` · Slug path: `{'/'.join(path)}`",
            "",
        ]
        if has_children:
            lines.extend(["## 子分类", ""])
            for c in node.children:
                lines.append(f"- [{c.title}]({c.slug}/_index.md)")
            lines.append("")
        if has_terminals:
            lines.extend(["## 本节文章", ""])
            for slug, title in sorted(terminals[path]):
                lines.append(f"- [{title}]({slug}.md)")
            lines.append("")
        _atomic_write_bytes(target_dir / "_index.md",
                            "\n".join(lines).encode("utf-8"))
        for c in node.children:
            _write_node(c, path)

    for sys_node in taxonomy.categories:
        _write_node(sys_node, ())

    # _uncategorized folder if any
    if ("_uncategorized",) in terminals:
        uc_dir = wiki_root / "_uncategorized"
        uc_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Uncategorized",
            "",
            "> 未匹配到任何 taxonomy 分类的文章",
            "",
            "## 文章列表",
            "",
        ]
        for slug, title in sorted(terminals[("_uncategorized",)]):
            lines.append(f"- [{title}]({slug}.md)")
        lines.append("")
        _atomic_write_bytes(uc_dir / "_index.md",
                            "\n".join(lines).encode("utf-8"))


def _serialize_taxonomy_v2_index(
    topics: list,
    entries: list,
    paths: list[tuple[str, ...]],
    provider_name: str,
    seed: int,
    sha_map: dict[str, str],
    taxonomy: TaxonomyConfigV2,
) -> bytes:
    obj = {
        "schema_version": _WIKI_INDEX_SCHEMA,
        "provider": provider_name,
        "seed": seed,
        "taxonomy_mode": True,
        "taxonomy_version": 2,
        "source_prd": taxonomy.source_prd,
        "source_pes_glob": taxonomy.source_pes_glob,
        "topics": [
            {
                "slug": t.slug,
                "title": t.title,
                "category_path": list(p),
                # Keep legacy ``category`` (used by ``verify_wiki``) = joined path
                "category": "/".join(p) if p else None,
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
            for t, e, p in zip(topics, entries, paths, strict=True)
        ],
    }
    return (
        json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
