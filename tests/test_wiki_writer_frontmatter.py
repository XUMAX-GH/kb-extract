from kb_extract.wiki.topics import EvidenceRef, Topic
from kb_extract.wiki.writer import build_topic_markdown


class _Llm:
    name = "fake"

    def chat(self, messages):
        return "Body text with a fact. [^ev-1]"


def _topic():
    ev = EvidenceRef(doc_id="DOC1", anchor="sec-0001",
                     section_title="3.2", page_start=6, page_end=6)
    return Topic(slug="hinge-torque", title="Hinge Torque", evidence=(ev,))


def test_topic_markdown_prepends_frontmatter_when_supplied():
    fm = "---\ntitle: Hinge Torque\n---\n"
    entry = build_topic_markdown(_topic(), _Llm(), frontmatter=fm,
                                 category_path=("bc", "mechanical"))
    assert entry.markdown.startswith("---\ntitle: Hinge Torque\n---\n")
    assert "# Hinge Torque" in entry.markdown


def test_topic_markdown_without_frontmatter_unchanged():
    entry = build_topic_markdown(_topic(), _Llm(),
                                 category_path=("bc", "mechanical"))
    assert entry.markdown.startswith("# Hinge Torque")
