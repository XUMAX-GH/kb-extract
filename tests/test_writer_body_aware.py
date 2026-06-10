"""Tests for body-aware wiki prompt construction (v0.6.0)."""

from __future__ import annotations

from pathlib import Path


def _make_kb(tmp_path: Path, doc_id: str, anchor: str, body: str) -> Path:
    """Create a minimal kb/<doc_id>/main.md with one anchored section."""
    kb_root = tmp_path / "kb"
    doc_dir = kb_root / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    main_md = doc_dir / "main.md"
    existing = main_md.read_text(encoding="utf-8") if main_md.exists() else ""
    main_md.write_text(
        existing + f'<a id="{anchor}"></a>\n{body}\n',
        encoding="utf-8",
    )
    return kb_root


def test_build_topic_markdown_passes_section_bodies_to_llm(tmp_path: Path) -> None:
    """The body excerpt for each evidence section must appear in the LLM prompt."""
    from kb_extract.wiki.providers.base import Message
    from kb_extract.wiki.topics import EvidenceRef, Topic
    from kb_extract.wiki.writer import build_topic_markdown

    kb_root = _make_kb(
        tmp_path,
        "docA",
        "sec-0001",
        "# Compliance\n\nAll devices must meet UL 60950-1 plus IEC 62368-1.",
    )
    _make_kb(
        tmp_path,
        "docB",
        "sec-0002",
        "# Safety Compliance\n\nEnclosure shall be flame-rated to UL 94V-0.",
    )

    topic = Topic(
        slug="compliance",
        title="compliance",
        evidence=(
            EvidenceRef("docA", "sec-0001", "Compliance", 1, 1),
            EvidenceRef("docB", "sec-0002", "Safety Compliance", 2, 2),
        ),
    )

    captured: list[list[Message]] = []

    class RecorderLlm:
        name = "recorder"

        def chat(self, messages: list[Message]) -> str:
            captured.append(messages)
            return "Devices must meet UL standards.[^ev-1] Enclosure flame-rated.[^ev-2]"

    entry = build_topic_markdown(topic, RecorderLlm(), kb_root=kb_root)

    assert captured, "LLM was called"
    user_msg = next(m for m in captured[0] if m["role"] == "user")
    # Both bodies must be in the prompt (verbatim excerpts)
    assert "UL 60950-1" in user_msg["content"]
    assert "UL 94V-0" in user_msg["content"]
    # The doc_id should be attributed so LLM knows which source said what
    assert "docA" in user_msg["content"]
    assert "docB" in user_msg["content"]
    # Final markdown should still include both footnotes
    assert "../kb/docA/main.md#sec-0001" in entry.markdown
    assert "../kb/docB/main.md#sec-0002" in entry.markdown


def test_build_topic_markdown_handles_missing_body_gracefully(tmp_path: Path) -> None:
    """A missing kb file should not crash; prompt just omits body excerpt."""
    from kb_extract.wiki.providers.base import Message
    from kb_extract.wiki.topics import EvidenceRef, Topic
    from kb_extract.wiki.writer import build_topic_markdown

    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    topic = Topic(
        slug="ghost",
        title="ghost",
        evidence=(EvidenceRef("missing-doc", "sec-0001", "Phantom", None, None),),
    )

    class StubLlm:
        name = "stub"

        def chat(self, messages: list[Message]) -> str:
            return "Some content.[^ev-1]"

    # Must not raise even though kb/missing-doc doesn't exist
    entry = build_topic_markdown(topic, StubLlm(), kb_root=kb_root)
    assert entry.pin_count == 1


def test_build_topic_markdown_backwards_compatible_without_kb_root(tmp_path: Path) -> None:
    """kb_root kwarg is optional — old call sites still work, just without body."""
    from kb_extract.wiki.providers.base import Message
    from kb_extract.wiki.topics import EvidenceRef, Topic
    from kb_extract.wiki.writer import build_topic_markdown

    topic = Topic(
        slug="t1",
        title="Topic 1",
        evidence=(EvidenceRef("docA", "sec-0001", "A Section", 1, 1),),
    )

    captured: list[list[Message]] = []

    class StubLlm:
        name = "stub"

        def chat(self, messages: list[Message]) -> str:
            captured.append(messages)
            return "claim.[^ev-1]"

    entry = build_topic_markdown(topic, StubLlm())  # no kb_root
    assert entry.pin_count == 1
    user_msg = next(m for m in captured[0] if m["role"] == "user")
    # Without kb_root, body section just isn't present (only the title line is)
    assert "A Section" in user_msg["content"]


def test_body_excerpt_capped_in_prompt(tmp_path: Path) -> None:
    """Per-evidence body excerpt should be capped to keep prompts bounded."""
    from kb_extract.wiki.providers.base import Message
    from kb_extract.wiki.topics import EvidenceRef, Topic
    from kb_extract.wiki.writer import build_topic_markdown

    huge = "x" * 10_000
    kb_root = _make_kb(tmp_path, "docA", "sec-0001", f"# Huge\n\n{huge}")

    topic = Topic(
        slug="huge",
        title="huge",
        evidence=(EvidenceRef("docA", "sec-0001", "Huge", 1, 1),),
    )

    captured: list[list[Message]] = []

    class StubLlm:
        name = "stub"

        def chat(self, messages: list[Message]) -> str:
            captured.append(messages)
            return "claim.[^ev-1]"

    build_topic_markdown(topic, StubLlm(), kb_root=kb_root)
    user_content = next(m["content"] for m in captured[0] if m["role"] == "user")
    # Total prompt should be much less than the raw 10 KB body
    assert len(user_content) < 5000
    # ellipsis indicates truncation
    assert "…" in user_content
