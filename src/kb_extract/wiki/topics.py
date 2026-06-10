"""Topic discovery —— 纯算法、无 LLM。

从 `kb/<doc>/index.json` 收集 section title，按词集合 Jaccard 距离做
single-linkage 聚类，每个簇产出一个 `Topic`。

确定性约束：
- 输入相同 -> 输出相同（含顺序）
- 不依赖 dict/set 迭代顺序（处处用 sorted）
- 不调任何 LLM / 随机数
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..layout import kb_dir as _kb_dir

# 极简中英停用词（够用即可，避免引入依赖）
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
        "by", "is", "are", "was", "were", "be", "as", "at", "this", "that",
        "it", "from", "into", "about", "introduction", "overview", "appendix",
        "chapter", "section", "part",
        "的", "了", "和", "及", "或", "与", "之", "其", "在", "对", "对于", "关于",
        "概述", "简介", "介绍", "附录", "章", "节", "部分", "总结",
    }
)

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff-]+")


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    doc_id: str
    anchor: str
    section_title: str
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True, slots=True)
class Topic:
    slug: str
    title: str
    evidence: tuple[EvidenceRef, ...]


def _tokenize(title: str) -> frozenset[str]:
    raw = _TOKEN_RE.findall(title.lower())
    return frozenset(t for t in raw if t and t not in _STOPWORDS and len(t) > 1)


def _jaccard_distance(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 1.0
    return 1.0 - inter / union


def _walk_index(node: dict, doc_id: str, out: list[tuple[EvidenceRef, frozenset[str]]]) -> None:
    """In-order walk, collecting leaves (nodes with no children) as evidence refs."""
    children = node.get("children") or []
    if not children:
        title = node.get("title", "") or ""
        anchor = node.get("anchor", "") or ""
        if not anchor:
            return  # 跳过没有 anchor 的虚拟根节点
        ev = EvidenceRef(
            doc_id=doc_id,
            anchor=anchor,
            section_title=title,
            page_start=node.get("page_start"),
            page_end=node.get("page_end"),
        )
        out.append((ev, _tokenize(title)))
        return
    for child in children:
        _walk_index(child, doc_id, out)


def _slugify(text: str, fallback: str) -> str:
    s = text.lower().strip()
    s = _SLUG_RE.sub("-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or fallback


_NUMERIC_TITLE_RE = re.compile(r"^[\d.\-\s]+$")


def _is_numeric_title(title: str) -> bool:
    """True when ``title`` is just digits / dots / dashes / whitespace.

    e.g. "1", "1.4", "1-4", "2.3.1", "  1.2  " — these come from spec
    sections numbered without a descriptive heading and contribute no
    semantic value to a wiki topic.
    """
    if not title.strip():
        return True
    return bool(_NUMERIC_TITLE_RE.match(title))


def discover_topics(
    project_root: Path,
    *,
    jaccard_threshold: float = 0.85,
    output_dir: Path | None = None,
    min_evidence: int = 1,
    skip_numeric_titles: bool = False,
) -> list[Topic]:
    """聚类 evidence；返回 slug 排序后的 Topic 列表。

    `jaccard_threshold` 是 single-linkage 的合并阈值（距离 ≤ 阈值则合并）。
    `output_dir` (v0.5.0): 当提供时，从 ``output_dir/kb/`` 而非
    ``project_root/kb/`` 读取索引。
    `min_evidence` (v0.6.0): 只保留 evidence 数 ≥ 该值的 topic（默认 1，
    兼容旧行为）。设为 2 可去掉单 evidence 的孤儿 topic。
    `skip_numeric_titles` (v0.6.0): 当为 True 时，丢弃标题仅由数字 / 点号 /
    短横线组成的 topic（如 "1"、"1.4"、"2.3.1"）。
    """
    kb_root = _kb_dir(project_root, output_dir)
    if not kb_root.is_dir():
        return []

    all_evidence: list[tuple[EvidenceRef, frozenset[str]]] = []
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        index_file = doc_dir / "index.json"
        if not index_file.is_file():
            continue
        try:
            root = json.loads(index_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        _walk_index(root, doc_dir.name, all_evidence)

    if not all_evidence:
        return []

    # Single-linkage 聚类：用 union-find
    n = len(all_evidence)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            # 总是把大编号挂到小编号下（保持确定性）
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            _, ti = all_evidence[i]
            _, tj = all_evidence[j]
            if _jaccard_distance(ti, tj) <= jaccard_threshold:
                union(i, j)

    # 收集每个簇
    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    topics: list[Topic] = []
    for root_idx in sorted(clusters.keys()):
        members = sorted(clusters[root_idx])
        # title = 簇里最常见的非停用词；如果并列，取字典序最小的
        word_count: dict[str, int] = defaultdict(int)
        for m in members:
            for w in all_evidence[m][1]:
                word_count[w] += 1
        if word_count:
            best = sorted(word_count.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        else:
            # 退化情形：标题全是停用词，用第一个 evidence 的 title 凑
            best = all_evidence[members[0]][0].section_title or f"topic-{root_idx}"
        slug = _slugify(best, f"topic-{root_idx:04d}")
        # 同 slug 去重（罕见但理论可能）
        title = best
        evidence = tuple(all_evidence[m][0] for m in members)
        topics.append(Topic(slug=slug, title=title, evidence=evidence))

    # 处理 slug 冲突
    seen: dict[str, int] = defaultdict(int)
    deduped: list[Topic] = []
    for t in topics:
        seen[t.slug] += 1
        if seen[t.slug] == 1:
            deduped.append(t)
        else:
            deduped.append(
                Topic(slug=f"{t.slug}-{seen[t.slug]}", title=t.title, evidence=t.evidence)
            )

    # v0.6.0 filters
    if min_evidence > 1 or skip_numeric_titles:
        filtered: list[Topic] = []
        for t in deduped:
            if len(t.evidence) < min_evidence:
                continue
            if skip_numeric_titles and _is_numeric_title(t.title):
                continue
            filtered.append(t)
        deduped = filtered

    deduped.sort(key=lambda t: t.slug)
    return deduped
