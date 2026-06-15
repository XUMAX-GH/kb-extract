"""Wiki entry writer + evidence resolver。

调 LLM 生成单个 topic 的 markdown，然后：
1. 解析 `[^ev-N]` pin
2. 在文末追加 `[^ev-N]: kb/<doc>/main.md#<anchor>` 脚注定义
3. 校验所有 pin 都解析得到（H14）

v0.6.0: ``build_topic_markdown`` 接受可选的 ``kb_root``，若提供则会从对应
section 读出正文摘录并喂给 LLM —— 真实 LLM 才能据此写出有信息量的内容。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .providers.base import LlmClient, Message
from .sections import read_section_body
from .topics import Topic

_PIN_RE = re.compile(r"\[\^ev-(\d+)\]")
# Per-section body excerpt cap. Combined with up to N evidence sections this
# bounds total prompt size to ~(N * 1200) chars + scaffolding.
_PER_BODY_CHARS = 1200
# Title-only fallback cap (legacy behavior when kb_root not supplied).
_MAX_EVIDENCE_CHARS = 1500


def _build_prompt(
    topic: Topic,
    kb_root: Path | None = None,
    *,
    category_title: str | None = None,
) -> list[Message]:
    sys_content = (
        "You are summarising technical hardware/firmware specification "
        "documentation. Every factual claim MUST be followed by a citation "
        "of the form [^ev-N] where N indexes the numbered evidence sections "
        "supplied below. Do NOT invent facts; if the evidence is thin, say "
        "so explicitly. Prefer concrete numbers, tolerances, standards "
        "(UL/IEC/MIL/etc), and named components over generalities. Reply in "
        "the same language as the topic title (Chinese title → Chinese body, "
        "English title → English body). Use markdown headings and short "
        "paragraphs. Target 200-400 words. Do NOT add a top-level # heading "
        "(the wrapper supplies one)."
    )
    if category_title:
        sys_content += (
            f"\n\nThis topic belongs to the **{category_title}** subsystem category. "
            "Focus your summary on aspects relevant to this subsystem."
        )
    sys_msg: Message = {"role": "system", "content": sys_content}
    lines = [
        f"Topic: {topic.title}",
        "",
        "Evidence sections (numbered):",
    ]
    for i, ev in enumerate(topic.evidence, start=1):
        page = ""
        if ev.page_start is not None:
            page = f" (p.{ev.page_start})"
        title = ev.section_title[:_MAX_EVIDENCE_CHARS]
        lines.append("")
        lines.append(f"[{i}] {title}{page}  —  source: {ev.doc_id}")
        if kb_root is not None:
            body = read_section_body(kb_root, ev.doc_id, ev.anchor, max_chars=_PER_BODY_CHARS)
            if body:
                lines.append("")
                lines.append("```")
                lines.append(body)
                lines.append("```")
    lines.append("")
    lines.append("Write a 200-400 word wiki entry. Use markdown.")
    user_msg: Message = {"role": "user", "content": "\n".join(lines)}
    return [sys_msg, user_msg]


@dataclass(frozen=True, slots=True)
class WikiEntry:
    topic_slug: str
    markdown: str
    pin_count: int
    unresolved_pins: tuple[int, ...]


def build_topic_markdown(
    topic: Topic,
    llm: LlmClient,
    *,
    kb_root: Path | None = None,
    category_slug: str | None = None,
    category_path: tuple[str, ...] | None = None,
    category_title: str | None = None,
) -> WikiEntry:
    """生成单个 topic 的完整 markdown（含 frontmatter + body + footnotes）。

    ``kb_root`` 可选；提供时 prompt 会包含每个 evidence section 的正文摘录。
    ``category_slug``: when set, footnote URLs are one level deeper:
    ``../../kb/<doc>/main.md#anchor`` instead of ``../kb/<doc>/main.md#anchor``.
    ``category_path`` (v0.9.0): tuple of slugs for hierarchical layouts (depth
    1..4). When supplied, takes precedence over ``category_slug`` and
    prepends ``"../" * len(path)`` to ``../kb`` so footnote URLs resolve
    correctly from arbitrarily nested ``wiki/sys/sub/part/.../topic.md``.
    ``category_title``: when set, adds subsystem context to the LLM prompt.
    """
    if not topic.evidence:
        raise ValueError(f"topic {topic.slug} has no evidence")

    messages = _build_prompt(topic, kb_root=kb_root, category_title=category_title)
    body = llm.chat(messages)

    # 收集 pin
    pin_numbers = sorted({int(m.group(1)) for m in _PIN_RE.finditer(body)})
    ev_count = len(topic.evidence)
    unresolved = tuple(n for n in pin_numbers if n < 1 or n > ev_count)

    # Hierarchical path takes precedence; fall back to legacy 1-level
    # ``category_slug``; otherwise flat layout.
    if category_path is not None:
        depth = len(category_path)
    elif category_slug:
        depth = 1
    else:
        depth = 0
    kb_prefix = "../" * depth + "../kb"

    # 构造 footnote 定义（按出现顺序）
    footnote_lines: list[str] = []
    for n in pin_numbers:
        if n < 1 or n > ev_count:
            footnote_lines.append(f"[^ev-{n}]: (UNRESOLVED — evidence index {n} out of range)")
            continue
        ev = topic.evidence[n - 1]
        url = f"{kb_prefix}/{ev.doc_id}/main.md#{ev.anchor}"
        page_hint = ""
        if ev.page_start is not None:
            page_hint = f" (p.{ev.page_start})"
        footnote_lines.append(
            f"[^ev-{n}]: [{ev.section_title}{page_hint}]({url})"
        )

    md_parts = [
        f"# {topic.title}",
        "",
        f"> Slug: `{topic.slug}` · Evidence sources: {ev_count}",
        "",
        body.strip(),
        "",
    ]
    if footnote_lines:
        md_parts.extend(footnote_lines)
        md_parts.append("")

    return WikiEntry(
        topic_slug=topic.slug,
        markdown="\n".join(md_parts),
        pin_count=len(pin_numbers),
        unresolved_pins=unresolved,
    )
