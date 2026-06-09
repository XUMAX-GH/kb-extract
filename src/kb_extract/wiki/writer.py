"""Wiki entry writer + evidence resolver。

调 LLM 生成单个 topic 的 markdown，然后：
1. 解析 `[^ev-N]` pin
2. 在文末追加 `[^ev-N]: kb/<doc>/main.md#<anchor>` 脚注定义
3. 校验所有 pin 都解析得到（H14）
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .providers.base import LlmClient, Message
from .topics import Topic

_PIN_RE = re.compile(r"\[\^ev-(\d+)\]")
_MAX_EVIDENCE_CHARS = 1500  # 每段截断，避免给 mock 灌过多文本


@dataclass(frozen=True, slots=True)
class WikiEntry:
    topic_slug: str
    markdown: str
    pin_count: int
    unresolved_pins: tuple[int, ...]


def _build_prompt(topic: Topic) -> list[Message]:
    sys_msg: Message = {
        "role": "system",
        "content": (
            "You are summarising technical documentation. Every factual claim MUST "
            "be followed by [^ev-N] where N indexes the evidence sections supplied "
            "below. Do not invent claims. Reply in the same language as the topic title."
        ),
    }
    lines = [f"Topic: {topic.title}", "", "Evidence sections (numbered):"]
    for i, ev in enumerate(topic.evidence, start=1):
        snippet = ev.section_title[:_MAX_EVIDENCE_CHARS]
        page = ""
        if ev.page_start is not None:
            page = f" (p.{ev.page_start})"
        lines.append(f"[{i}] {snippet}{page}")
    lines.append("")
    lines.append("Write a 200-400 word wiki entry. Use markdown.")
    user_msg: Message = {"role": "user", "content": "\n".join(lines)}
    return [sys_msg, user_msg]


def build_topic_markdown(topic: Topic, llm: LlmClient) -> WikiEntry:
    """生成单个 topic 的完整 markdown（含 frontmatter + body + footnotes）。"""
    if not topic.evidence:
        raise ValueError(f"topic {topic.slug} has no evidence")

    messages = _build_prompt(topic)
    body = llm.chat(messages)

    # 收集 pin
    pin_numbers = sorted({int(m.group(1)) for m in _PIN_RE.finditer(body)})
    ev_count = len(topic.evidence)
    unresolved = tuple(n for n in pin_numbers if n < 1 or n > ev_count)

    # 构造 footnote 定义（按出现顺序）
    footnote_lines: list[str] = []
    for n in pin_numbers:
        if n < 1 or n > ev_count:
            footnote_lines.append(f"[^ev-{n}]: (UNRESOLVED — evidence index {n} out of range)")
            continue
        ev = topic.evidence[n - 1]
        url = f"../kb/{ev.doc_id}/main.md#{ev.anchor}"
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
