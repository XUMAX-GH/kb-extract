# Precise Requirement Evidence + Obsidian-Compatible Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make extracted requirements traceable to the exact verbatim source sentence, and evolve the existing `kb wiki build` (v2 hierarchical) output into an Obsidian-compatible, cross-domain-linked knowledge base.

**Architecture:** Both features live entirely in the wiki enrichment layer (`src/kb_extract/wiki/`); the deterministic core (`kb/main.md` + `sec-NNNN` anchors) is never modified. F1 adds a deterministically-verified verbatim quote to each requirement. F2 adds YAML frontmatter, `[[wikilinks]]`, `index.md`/`log.md`, and LLM-authored entity/concept aggregation pages to the v2 build (`build_wiki_v2`), keeping `wiki verify` (anchor-based) green.

**Tech Stack:** Python 3.11, dataclasses, `uv` + `pytest` (`--disable-socket`), `ruff`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-25-precise-evidence-and-obsidian-wiki-design.md`

**Hardness rules (AGENTS.md):** English code/tests/commits; Chinese user-facing docs; byte-identical output (sorted lists, fixed key order, LF, `serialize_markdown`); no fancy unicode in commits (use `x` / `->` / `sec.`); no direct push to main (PR per phase). Gate before any completion claim: `uv run pytest` and `uv run ruff check .`.

**Conventions observed (follow these):**
- Tests live flat in `tests/test_<area>.py`, plain `def test_...()`, import from `kb_extract...`.
- All markdown writes go through `serialize_markdown(...)` then `.encode("utf-8")`.
- JSON writes use `sort_keys=True, ensure_ascii=False, indent=2` + trailing `\n`.
- Run a single test: `uv run pytest tests/test_file.py::test_name -v`.

---

## File Structure

**F1 (requirements precise evidence):**
- Modify `src/kb_extract/wiki/requirements/models.py` - add `find_verbatim`, `TestItem.evidence_quote`, coerce logic.
- Modify `src/kb_extract/wiki/requirements/render.py` - render/omit quote blockquote; JSON key.
- Modify `src/kb_extract/wiki/requirements/assets/user_template.md` and `assets/output_schema.json` - request `EvidenceQuote`.
- Tests: `tests/test_requirements_models.py` (new), extend `tests/test_requirements_render.py`.

**F2-A (Obsidian skeleton, deterministic):**
- Create `src/kb_extract/wiki/frontmatter.py` - build + serialize YAML frontmatter.
- Create `src/kb_extract/wiki/wikilink.py` - `to_wikilink`.
- Create `src/kb_extract/wiki/catalog.py` - `render_index_md`, `append_log_entry`.
- Modify `src/kb_extract/wiki/writer.py` - `build_topic_markdown` accepts `frontmatter`.
- Modify `src/kb_extract/wiki/orchestrator.py` - compute per-topic frontmatter, wikilink `_index.md`, write `index.md` + `log.md`, thread a `build_date` param.
- Tests: `tests/test_wiki_frontmatter.py`, `tests/test_wiki_wikilink.py`, `tests/test_wiki_catalog.py` (new).

**F2-B (entity/concept pages + wikilink verify):**
- Create `src/kb_extract/wiki/entities.py` - `extract_candidates`, `build_aggregation_pages`.
- Modify `src/kb_extract/wiki/orchestrator.py` - call entity build; add `verify_wikilinks`.
- Tests: `tests/test_wiki_entities.py`, `tests/test_wiki_wikilink_verify.py` (new).

**Final:**
- Rebuild k-bur demo; update `README.md` (Chinese).

---

## PHASE F1: Precise requirement evidence

### Task 1: `find_verbatim` helper

**Files:**
- Modify: `src/kb_extract/wiki/requirements/models.py`
- Test: `tests/test_requirements_models.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_requirements_models.py`:

```python
from kb_extract.wiki.requirements.models import find_verbatim


def test_find_verbatim_exact_substring_returns_original():
    body = "The torque shall be 5 Nm.\nMeasured per spec."
    assert find_verbatim("The torque shall be 5 Nm.", body) == "The torque shall be 5 Nm."


def test_find_verbatim_normalizes_whitespace_but_returns_original_span():
    body = "Stiffness   >=  5\n  N/mm across the hinge."
    # Quote uses single spaces; body has runs of whitespace + newline.
    got = find_verbatim("Stiffness >= 5 N/mm", body)
    assert got == "Stiffness   >=  5\n  N/mm"


def test_find_verbatim_not_present_returns_none():
    body = "The torque shall be 5 Nm."
    assert find_verbatim("The mass shall be 200 g.", body) is None


def test_find_verbatim_empty_quote_returns_none():
    assert find_verbatim("", "anything") is None
    assert find_verbatim("   ", "anything") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_requirements_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_verbatim'`.

- [ ] **Step 3: Write minimal implementation**

In `src/kb_extract/wiki/requirements/models.py`, after the imports (after the `_FENCE_RE` line) add:

```python
_WS_RE = re.compile(r"\s+")


def find_verbatim(quote: str, body: str) -> str | None:
    """Return the original span of ``body`` matching ``quote`` ignoring only
    whitespace differences, or ``None`` if there is no match.

    Both strings are whitespace-normalized (runs of whitespace -> single
    space, stripped) for comparison, but the returned value is the ORIGINAL
    text from ``body`` (so rendering preserves the source exactly). This is the
    zero-hallucination guard: an unverifiable quote yields ``None`` and is
    dropped by the caller -- never approximated.
    """
    q = _WS_RE.sub(" ", quote).strip()
    if not q:
        return None
    # Walk the body once, building a normalized string plus an index map back
    # to original character offsets, so we can recover the exact source span.
    norm_chars: list[str] = []
    orig_index: list[int] = []
    prev_ws = False
    for i, ch in enumerate(body):
        if ch.isspace():
            if not prev_ws and norm_chars:
                norm_chars.append(" ")
                orig_index.append(i)
            prev_ws = True
        else:
            norm_chars.append(ch)
            orig_index.append(i)
            prev_ws = False
    norm = "".join(norm_chars)
    pos = norm.find(q)
    if pos < 0:
        return None
    start = orig_index[pos]
    end = orig_index[pos + len(q) - 1] + 1
    return body[start:end]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_requirements_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/test_requirements_models.py src/kb_extract/wiki/requirements/models.py
git commit -m "feat(requirements): add find_verbatim whitespace-tolerant source matcher" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: `TestItem.evidence_quote` field + coerce logic

**Files:**
- Modify: `src/kb_extract/wiki/requirements/models.py`
- Test: `tests/test_requirements_models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_requirements_models.py`:

```python
from kb_extract.wiki.requirements.models import TestItem, coerce_item


def test_coerce_item_keeps_verifiable_quote():
    body = "The hinge torque shall be 5 Nm at room temperature."
    obj = {
        "Function": "Torque",
        "What": "Hinge torque 5 Nm",
        "EvidenceQuote": "The hinge torque shall be 5 Nm",
    }
    item = coerce_item(obj, anchor="sec-0003", section_title="3.2",
                       category="Mechanical", section_body=body)
    assert item.evidence_quote == "The hinge torque shall be 5 Nm"


def test_coerce_item_drops_unverifiable_quote():
    body = "The hinge torque shall be 5 Nm."
    obj = {"What": "X", "EvidenceQuote": "totally invented sentence"}
    item = coerce_item(obj, anchor="sec-0003", section_title="3.2",
                       category="Mechanical", section_body=body)
    assert item.evidence_quote == ""


def test_coerce_item_missing_quote_is_empty():
    item = coerce_item({"What": "X"}, anchor="sec-0003", section_title="3.2",
                       category="Mechanical", section_body="body")
    assert item.evidence_quote == ""


def test_to_dict_includes_evidence_quote():
    it = TestItem(category="C", function="F", what="W", how="H",
                  sample_size="S", source_document="D", source_section="3.2",
                  evidence_ref="sec-0001", evidence_quote="Q")
    assert it.to_dict()["EvidenceQuote"] == "Q"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_requirements_models.py -v`
Expected: FAIL - `TypeError` (TestItem has no `evidence_quote`) and `coerce_item()` got unexpected keyword `section_body`.

- [ ] **Step 3: Write minimal implementation**

In `src/kb_extract/wiki/requirements/models.py`:

3a. Add the field to the dataclass (after `evidence_ref: str`):

```python
    evidence_ref: str
    evidence_quote: str = ""
```

3b. Add the key to `to_dict` (after the `"EvidenceRef"` entry, keep insertion order):

```python
            "EvidenceRef": self.evidence_ref,
            "EvidenceQuote": self.evidence_quote,
```

3c. Update `coerce_item` signature and body. Replace the existing signature line and the `return TestItem(...)` block:

```python
def coerce_item(
    obj: dict,
    *,
    anchor: str,
    section_title: str,
    category: str | None = None,
    section_body: str = "",
) -> TestItem:
```

and at the end, before building the item, compute the verified quote, then pass it:

```python
    raw_quote = s("EvidenceQuote")
    verified = find_verbatim(raw_quote, section_body) if raw_quote else None

    return TestItem(
        category=cat,
        function=s("Function"),
        what=s("What"),
        how=s("How") or DEFAULT_HOW,
        sample_size=s("Sample Size") or DEFAULT_SAMPLE,
        source_document=s("SourceDocument") or DEFAULT_DOC,
        source_section=section_title or s("SourceSection"),
        evidence_ref=anchor,  # ALWAYS the real anchor; never trust LLM
        evidence_quote=verified or "",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_requirements_models.py -v`
Expected: PASS (8 passed total).

- [ ] **Step 5: Commit**

```bash
git add tests/test_requirements_models.py src/kb_extract/wiki/requirements/models.py
git commit -m "feat(requirements): add verified evidence_quote field to TestItem" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Thread `section_body` into extractor + request quote in prompt

**Files:**
- Modify: `src/kb_extract/wiki/requirements/extractor.py:75-83`
- Modify: `src/kb_extract/wiki/requirements/assets/user_template.md`
- Modify: `src/kb_extract/wiki/requirements/assets/output_schema.json`
- Test: `tests/test_requirements_extractor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_requirements_extractor.py` (match the file's existing fixture style; this standalone test builds a tiny kb tree):

```python
from pathlib import Path

from kb_extract.wiki.requirements.extractor import extract_requirements


class _QuoteLlm:
    name = "fake"

    def chat(self, messages):
        # Return one item whose EvidenceQuote is a real substring of the body.
        return (
            '[{"Function":"Torque","What":"Hinge torque 5 Nm",'
            '"EvidenceQuote":"hinge torque shall be 5 Nm"}]'
        )


def test_extractor_populates_verified_quote(tmp_path: Path):
    kb = tmp_path / "kb" / "DOC1"
    kb.mkdir(parents=True)
    (kb / "main.md").write_text(
        '<a id="sec-0001"></a>\n# Mechanical\n\n'
        "The hinge torque shall be 5 Nm at room temperature.\n",
        encoding="utf-8",
    )
    res = extract_requirements(tmp_path, _QuoteLlm())
    items = res.items_by_doc["DOC1"]
    assert items[0].evidence_quote == "hinge torque shall be 5 Nm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_requirements_extractor.py::test_extractor_populates_verified_quote -v`
Expected: FAIL - `evidence_quote` is `""` because the extractor does not yet pass `section_body` to `coerce_item`.

- [ ] **Step 3: Write minimal implementation**

3a. In `src/kb_extract/wiki/requirements/extractor.py`, update the `coerce_item` call (currently lines 77-83) to pass the chunk body:

```python
                    for obj in parse_items(raw):
                        items.append(
                            coerce_item(
                                obj,
                                anchor=sec.anchor,
                                section_title=sec.title,
                                category=sec.category,
                                section_body=chunk,
                            )
                        )
```

3b. In `src/kb_extract/wiki/requirements/assets/output_schema.json`, add `EvidenceQuote` to `required` and `properties` (keep `additionalProperties: false`):

In `required`, append `"EvidenceQuote"`. In `properties`, add after `EvidenceRef`:

```json
    "EvidenceQuote": {
      "type": "string",
      "description": "A single sentence or table row copied VERBATIM (exactly, no paraphrase) from the provided section text that most directly supports this requirement. Must be a literal substring of the section content."
    }
```

3c. In `src/kb_extract/wiki/requirements/assets/user_template.md`, add a new bullet under the `### Task` section, right after the `CRITICAL:` line:

```markdown
- For each item also return `EvidenceQuote`: copy ONE sentence or table row VERBATIM (exactly as written, no paraphrase) from the section content above that most directly supports the requirement. It must be a literal substring of the provided text.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_requirements_extractor.py -v`
Expected: PASS (existing tests + new one).

- [ ] **Step 5: Commit**

```bash
git add tests/test_requirements_extractor.py src/kb_extract/wiki/requirements/extractor.py src/kb_extract/wiki/requirements/assets/output_schema.json src/kb_extract/wiki/requirements/assets/user_template.md
git commit -m "feat(requirements): request and thread verbatim EvidenceQuote through extraction" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Render the quote blockquote + JSON key

**Files:**
- Modify: `src/kb_extract/wiki/requirements/render.py:31-38`
- Test: `tests/test_requirements_render.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_requirements_render.py`:

```python
def test_markdown_renders_evidence_quote_blockquote():
    md = render_markdown("DOC1", [_item(evidence_quote="hinge torque is 5 Nm")])
    assert "  - Evidence: > hinge torque is 5 Nm" in md


def test_markdown_omits_quote_line_when_empty():
    md = render_markdown("DOC1", [_item(evidence_quote="")])
    assert "Evidence:" not in md


def test_json_includes_evidence_quote_key():
    out = render_json([_item(evidence_quote="Q")])
    assert '"EvidenceQuote": "Q"' in out
```

(The shared `_item(...)` helper at the top of this file passes `**kw` to `TestItem`, so `evidence_quote=...` flows through once Task 2 added the field default.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_requirements_render.py -v`
Expected: FAIL - the `Evidence:` line is not emitted.

- [ ] **Step 3: Write minimal implementation**

In `src/kb_extract/wiki/requirements/render.py`, inside `render_markdown`, in the per-item loop, after the `Source:` line (current line 37) add:

```python
            lines.append(f"  - Source: {it.source_document} / {it.source_section}")
            if it.evidence_quote:
                lines.append(f"  - Evidence: > {it.evidence_quote}")
            lines.append("")
```

(`render_json` already serializes `to_dict()`, which now includes `EvidenceQuote` from Task 2 - no change needed there.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_requirements_render.py -v`
Expected: PASS.

- [ ] **Step 5: Full gate + commit**

Run: `uv run pytest` then `uv run ruff check .`
Expected: all pass, ruff clean.

```bash
git add tests/test_requirements_render.py src/kb_extract/wiki/requirements/render.py
git commit -m "feat(requirements): render verified evidence quote as blockquote" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

**End of F1.** Open a PR for `feat/precise-evidence-obsidian-wiki` -> main covering Tasks 1-4 (or continue and PR the whole branch at the end - follow the chosen workflow).

---

## PHASE F2-A: Obsidian deterministic skeleton

### Task 5: `frontmatter.py`

**Files:**
- Create: `src/kb_extract/wiki/frontmatter.py`
- Test: `tests/test_wiki_frontmatter.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_frontmatter.py`:

```python
from kb_extract.wiki.frontmatter import build_frontmatter, render_frontmatter


def test_build_frontmatter_sorts_and_dedupes_lists():
    fm = build_frontmatter(
        title="Hinge Torque",
        category_path=("bc", "mechanical"),
        slug="hinge-torque",
        doc_ids=["DOC2", "DOC1", "DOC1"],
        extra_tags=["concept/torque"],
    )
    assert fm["domain"] == "bc"
    assert fm["category_path"] == "bc/mechanical"
    assert fm["evidence_sources"] == ["DOC1", "DOC2"]
    # tags: domain + each path segment + extra, sorted + unique
    assert fm["tags"] == sorted({
        "domain/bc", "path/bc", "path/mechanical", "concept/torque",
    })


def test_render_frontmatter_is_deterministic_yaml_block():
    fm = build_frontmatter(
        title="T", category_path=("bc",), slug="t", doc_ids=["D1"],
    )
    out = render_frontmatter(fm)
    assert out.startswith("---\n")
    assert out.endswith("---\n")
    assert "\r" not in out
    # Stable key order: title, type, domain, category_path, slug,
    # evidence_sources, tags
    lines = out.splitlines()
    assert lines[1].startswith("title:")
    assert lines[2].startswith("type:")
    # Identical input -> identical output
    assert render_frontmatter(build_frontmatter(
        title="T", category_path=("bc",), slug="t", doc_ids=["D1"])) == out


def test_render_frontmatter_quotes_title_with_special_chars():
    fm = build_frontmatter(title="A: B #1", category_path=("bc",), slug="x",
                           doc_ids=[])
    out = render_frontmatter(fm)
    assert 'title: "A: B #1"' in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_frontmatter.py -v`
Expected: FAIL - module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `src/kb_extract/wiki/frontmatter.py`:

```python
"""Deterministic YAML frontmatter for Obsidian-compatible wiki pages.

Hand-rolled emitter (no PyYAML dependency) with a fixed key order and sorted
list values so output is byte-identical across platforms (H13).
"""

from __future__ import annotations

# Fixed emission order. Keys absent from a given frontmatter dict are skipped.
_KEY_ORDER = (
    "title",
    "type",
    "domain",
    "category_path",
    "slug",
    "evidence_sources",
    "tags",
)

_NEEDS_QUOTE = set(':#[]{}",&*!|>%@`')


def build_frontmatter(
    *,
    title: str,
    category_path: tuple[str, ...],
    slug: str,
    doc_ids: list[str],
    page_type: str = "topic",
    extra_tags: list[str] | None = None,
) -> dict[str, object]:
    """Build a frontmatter dict from deterministic topic metadata."""
    domain = category_path[0] if category_path else "_uncategorized"
    tags = {f"domain/{domain}"}
    for seg in category_path:
        tags.add(f"path/{seg}")
    for t in extra_tags or []:
        tags.add(t)
    return {
        "title": title,
        "type": page_type,
        "domain": domain,
        "category_path": "/".join(category_path) if category_path else domain,
        "slug": slug,
        "evidence_sources": sorted(set(doc_ids)),
        "tags": sorted(tags),
    }


def _scalar(value: str) -> str:
    if value == "" or any(c in _NEEDS_QUOTE for c in value) or value != value.strip():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def render_frontmatter(fm: dict[str, object]) -> str:
    """Render a frontmatter dict to a deterministic ``---`` YAML block."""
    lines = ["---"]
    for key in _KEY_ORDER:
        if key not in fm:
            continue
        val = fm[key]
        if isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            else:
                rendered = ", ".join(_scalar(str(v)) for v in val)
                lines.append(f"{key}: [{rendered}]")
        else:
            lines.append(f"{key}: {_scalar(str(val))}")
    lines.append("---")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_frontmatter.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_frontmatter.py src/kb_extract/wiki/frontmatter.py
git commit -m "feat(wiki): add deterministic YAML frontmatter emitter" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: `wikilink.py`

**Files:**
- Create: `src/kb_extract/wiki/wikilink.py`
- Test: `tests/test_wiki_wikilink.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_wikilink.py`:

```python
from kb_extract.wiki.wikilink import to_wikilink


def test_to_wikilink_with_label():
    assert to_wikilink("mechanical/_index", "MECHANICAL") == "[[mechanical/_index|MECHANICAL]]"


def test_to_wikilink_label_equals_target_omits_pipe():
    assert to_wikilink("hinge-torque", "hinge-torque") == "[[hinge-torque]]"


def test_to_wikilink_strips_md_extension():
    assert to_wikilink("hinge-torque.md", "Hinge") == "[[hinge-torque|Hinge]]"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_wikilink.py -v`
Expected: FAIL - module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `src/kb_extract/wiki/wikilink.py`:

```python
"""Obsidian wikilink formatting helper.

Obsidian resolves ``[[target]]`` by note path/name. We always emit a
relative-style target (without the ``.md`` extension) and an optional display
label.
"""

from __future__ import annotations


def to_wikilink(target: str, label: str) -> str:
    """Return an Obsidian ``[[target|label]]`` (or ``[[target]]`` when equal)."""
    if target.endswith(".md"):
        target = target[: -len(".md")]
    if label == target:
        return f"[[{target}]]"
    return f"[[{target}|{label}]]"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_wikilink.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_wikilink.py src/kb_extract/wiki/wikilink.py
git commit -m "feat(wiki): add Obsidian wikilink formatter" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: `build_topic_markdown` prepends frontmatter

**Files:**
- Modify: `src/kb_extract/wiki/writer.py:87-160`
- Test: `tests/test_wiki_writer_frontmatter.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_writer_frontmatter.py`:

```python
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
    # The H1 title still follows the frontmatter.
    assert "# Hinge Torque" in entry.markdown


def test_topic_markdown_without_frontmatter_unchanged():
    entry = build_topic_markdown(_topic(), _Llm(),
                                 category_path=("bc", "mechanical"))
    assert entry.markdown.startswith("# Hinge Torque")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_writer_frontmatter.py -v`
Expected: FAIL - `build_topic_markdown()` got an unexpected keyword `frontmatter`.

- [ ] **Step 3: Write minimal implementation**

In `src/kb_extract/wiki/writer.py`:

3a. Add `frontmatter` to the signature (after `category_title`):

```python
    category_title: str | None = None,
    frontmatter: str | None = None,
) -> WikiEntry:
```

3b. Change the `md_parts` construction. Replace:

```python
    md_parts = [
        f"# {topic.title}",
        "",
        f"> Slug: `{topic.slug}` · Evidence sources: {ev_count}",
        "",
        body.strip(),
        "",
    ]
```

with:

```python
    md_parts: list[str] = []
    if frontmatter:
        md_parts.append(frontmatter.rstrip("\n"))
        md_parts.append("")
    md_parts.extend([
        f"# {topic.title}",
        "",
        f"> Slug: `{topic.slug}` · Evidence sources: {ev_count}",
        "",
        body.strip(),
        "",
    ])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_writer_frontmatter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_writer_frontmatter.py src/kb_extract/wiki/writer.py
git commit -m "feat(wiki): allow build_topic_markdown to prepend frontmatter" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Wire frontmatter into `build_wiki_v2` topic writes

**Files:**
- Modify: `src/kb_extract/wiki/orchestrator.py:710-716` (topic build call)
- Test: `tests/test_wiki_v2_frontmatter.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_v2_frontmatter.py`. Reuse the existing v2 e2e fixture pattern; this asserts a generated topic page carries frontmatter. Inspect `tests/test_wiki_v2_e2e.py` for the exact fixture helper and mirror it. Minimal shape:

```python
from pathlib import Path

from kb_extract.wiki.orchestrator import build_wiki_v2
from kb_extract.wiki.taxonomy import TaxonomyConfigV2  # adjust to real import


def test_v2_topic_pages_have_frontmatter(tmp_path: Path):
    # Build a minimal kb/ tree + taxonomy exactly like test_wiki_v2_e2e.py does,
    # then:
    build_wiki_v2(tmp_path, taxonomy=..., provider="mock", output_dir=tmp_path)
    pages = [p for p in (tmp_path / "wiki").rglob("*.md")
             if p.name != "_index.md"]
    assert pages, "expected at least one topic page"
    text = pages[0].read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "category_path:" in text
    assert "tags:" in text
```

NOTE for implementer: open `tests/test_wiki_v2_e2e.py` and copy its fixture
construction (kb tree + `TaxonomyConfigV2` build) verbatim into the `...`
placeholders before running. Do not invent taxonomy shapes.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_v2_frontmatter.py -v`
Expected: FAIL - pages start with `# <title>`, not `---`.

- [ ] **Step 3: Write minimal implementation**

3a. At the top of `src/kb_extract/wiki/orchestrator.py` add the import (near the other wiki imports):

```python
from .frontmatter import build_frontmatter, render_frontmatter
```

3b. In `build_wiki_v2`, replace the `entry = build_topic_markdown(...)` call (lines ~712-716) with one that computes frontmatter:

```python
            fm = render_frontmatter(build_frontmatter(
                title=best,
                category_path=cat_path,
                slug=topic_slug,
                doc_ids=[ev.doc_id for ev in cluster_evs],
            ))
            entry = build_topic_markdown(
                topic, llm, kb_root=kb_root,
                category_path=cat_path,
                category_title=cat_title,
                frontmatter=fm,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_v2_frontmatter.py -v`
Expected: PASS.

Also run the existing e2e to confirm no regression:
Run: `uv run pytest tests/test_wiki_v2_e2e.py -v`
Expected: PASS (verify still green; frontmatter does not affect anchor checks).

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_v2_frontmatter.py src/kb_extract/wiki/orchestrator.py
git commit -m "feat(wiki): emit frontmatter on v2 topic pages" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: Wikilinks + frontmatter in `_index.md` pages

**Files:**
- Modify: `src/kb_extract/wiki/orchestrator.py:802-893` (`_write_v2_indices`)
- Test: `tests/test_wiki_v2_indices.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_v2_indices.py`. Again mirror the e2e fixture. Assert the root and node `_index.md` use wikilinks:

```python
from pathlib import Path

from kb_extract.wiki.orchestrator import build_wiki_v2


def test_index_pages_use_wikilinks(tmp_path: Path):
    # Build minimal kb + taxonomy as in test_wiki_v2_e2e.py:
    build_wiki_v2(tmp_path, taxonomy=..., provider="mock", output_dir=tmp_path)
    root_idx = (tmp_path / "wiki" / "_index.md").read_text(encoding="utf-8")
    assert "[[" in root_idx and "]]" in root_idx
    # Old relative-md link form must be gone from navigation lists.
    assert "/_index.md)" not in root_idx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_v2_indices.py -v`
Expected: FAIL - indices currently use `[title](slug/_index.md)`.

- [ ] **Step 3: Write minimal implementation**

In `_write_v2_indices` (`src/kb_extract/wiki/orchestrator.py`):

3a. Add import usage of `to_wikilink` at top of file:

```python
from .wikilink import to_wikilink
```

3b. Replace the root system list line:

```python
    for sys_node in taxonomy.categories:
        root_lines.append(f"- [{sys_node.title}]({sys_node.slug}/_index.md)")
```

with:

```python
    for sys_node in taxonomy.categories:
        root_lines.append(
            f"- {to_wikilink(f'{sys_node.slug}/_index', sys_node.title)}"
        )
```

3c. Replace the uncategorized root list line:

```python
        for slug, title in sorted(uncategorized):
            root_lines.append(f"- [{title}](_uncategorized/{slug}.md)")
```

with:

```python
        for slug, title in sorted(uncategorized):
            root_lines.append(
                f"- {to_wikilink(f'_uncategorized/{slug}', title)}"
            )
```

3d. In `_write_node`, replace the child list:

```python
            for c in node.children:
                lines.append(f"- [{c.title}]({c.slug}/_index.md)")
```

with:

```python
            for c in node.children:
                lines.append(
                    f"- {to_wikilink(f'{c.slug}/_index', c.title)}"
                )
```

3e. In `_write_node`, replace the terminal-topic list:

```python
            for slug, title in sorted(terminals[path]):
                lines.append(f"- [{title}]({slug}.md)")
```

with:

```python
            for slug, title in sorted(terminals[path]):
                lines.append(f"- {to_wikilink(slug, title)}")
```

3f. In the `_uncategorized` block at the end, replace:

```python
        for slug, title in sorted(terminals[("_uncategorized",)]):
            lines.append(f"- [{title}]({slug}.md)")
```

with:

```python
        for slug, title in sorted(terminals[("_uncategorized",)]):
            lines.append(f"- {to_wikilink(slug, title)}")
```

3g. Add an index-page frontmatter at the top of each node `_index.md`. In `_write_node`, change the `lines = [...]` initializer to prepend frontmatter:

```python
        fm = render_frontmatter(build_frontmatter(
            title=node.title,
            category_path=path,
            slug=node.slug,
            doc_ids=[],
            page_type="index",
        ))
        lines = [
            fm.rstrip("\n"),
            "",
            f"# {node.title}",
            "",
            f"> Layer: `{node.layer}` · Slug path: `{'/'.join(path)}`",
            "",
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_v2_indices.py tests/test_wiki_v2_e2e.py -v`
Expected: PASS (both the new assertion and the existing e2e/verify).

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_v2_indices.py src/kb_extract/wiki/orchestrator.py
git commit -m "feat(wiki): use wikilinks and frontmatter in v2 index pages" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 10: `catalog.py` - `index.md` + `log.md`

**Files:**
- Create: `src/kb_extract/wiki/catalog.py`
- Test: `tests/test_wiki_catalog.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_catalog.py`:

```python
from kb_extract.wiki.catalog import render_index_md, render_log_entry


def test_render_index_md_groups_by_domain_sorted():
    rows = [
        ("software", "Boot Sequence", "software/boot", ["D1"]),
        ("mechanical", "Hinge Torque", "mechanical/hinge", ["D2", "D1"]),
        ("mechanical", "Keyset Force", "mechanical/keyset", ["D3"]),
    ]
    md = render_index_md(rows)
    assert md.startswith("# ")
    # Domains sorted; mechanical before software.
    assert md.index("mechanical") < md.index("software")
    # Each row uses a wikilink.
    assert "[[mechanical/hinge|Hinge Torque]]" in md
    assert "\r" not in md


def test_render_log_entry_uses_injected_date_and_prefix():
    line = render_log_entry(date="2026-06-25", provider="cached",
                            topics=188, pins=245)
    assert line == "## [2026-06-25] build | provider=cached, topics=188, pins=245"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_catalog.py -v`
Expected: FAIL - module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `src/kb_extract/wiki/catalog.py`:

```python
"""Karpathy-style wiki navigation files: content catalog + chronological log.

``index.md`` is a content-oriented catalog (one line per page, grouped by
domain). ``log.md`` is an append-only chronological record; the date is
injected (never read from the wall clock) so output stays byte-reproducible.
"""

from __future__ import annotations

from collections import defaultdict

from .wikilink import to_wikilink

# row = (domain, title, slug_path_for_link, doc_ids)
CatalogRow = tuple[str, str, str, list[str]]


def render_index_md(rows: list[CatalogRow]) -> str:
    """Render the wiki catalog grouped by domain, deterministically ordered."""
    by_domain: dict[str, list[CatalogRow]] = defaultdict(list)
    for row in rows:
        by_domain[row[0]].append(row)
    lines = ["# Wiki Index", ""]
    for domain in sorted(by_domain):
        lines.append(f"## {domain}")
        lines.append("")
        for _dom, title, link_path, doc_ids in sorted(
            by_domain[domain], key=lambda r: (r[1], r[2])
        ):
            src = ", ".join(sorted(set(doc_ids)))
            suffix = f" - sources: {src}" if src else ""
            lines.append(f"- {to_wikilink(link_path, title)}{suffix}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def render_log_entry(*, date: str, provider: str, topics: int, pins: int) -> str:
    """Render one append-only log line (parseable via ``grep '^## \\['``)."""
    return f"## [{date}] build | provider={provider}, topics={topics}, pins={pins}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_catalog.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_catalog.py src/kb_extract/wiki/catalog.py
git commit -m "feat(wiki): add index.md catalog and log.md entry renderers" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 11: Write `index.md` + append `log.md` in `build_wiki_v2`

**Files:**
- Modify: `src/kb_extract/wiki/orchestrator.py:576-783` (`build_wiki_v2` signature + write section)
- Test: `tests/test_wiki_v2_catalog.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_v2_catalog.py` (mirror e2e fixture):

```python
from pathlib import Path

from kb_extract.wiki.orchestrator import build_wiki_v2


def test_build_writes_index_and_log(tmp_path: Path):
    # Build minimal kb + taxonomy as in test_wiki_v2_e2e.py:
    build_wiki_v2(tmp_path, taxonomy=..., provider="mock", output_dir=tmp_path,
                  build_date="2026-06-25")
    wiki = tmp_path / "wiki"
    assert (wiki / "index.md").is_file()
    log = (wiki / "log.md").read_text(encoding="utf-8")
    assert "## [2026-06-25] build |" in log


def test_log_is_append_only(tmp_path: Path):
    # Build twice; the second build must keep the first line and add a second.
    build_wiki_v2(tmp_path, taxonomy=..., provider="mock", output_dir=tmp_path,
                  build_date="2026-06-25")
    build_wiki_v2(tmp_path, taxonomy=..., provider="mock", output_dir=tmp_path,
                  build_date="2026-06-26")
    log = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert log.count("## [") == 2
    assert "2026-06-25" in log and "2026-06-26" in log
```

NOTE: the existing wiki clean step deletes everything in `wiki/` at build start
(lines 733-738). To keep `log.md` append-only, the implementation must read the
old `log.md` BEFORE the clean step and re-write it after.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_v2_catalog.py -v`
Expected: FAIL - `build_wiki_v2()` got unexpected keyword `build_date`; no `index.md`/`log.md`.

- [ ] **Step 3: Write minimal implementation**

3a. Add the import at top of `orchestrator.py`:

```python
from .catalog import render_index_md, render_log_entry
```

3b. Add `build_date` to the `build_wiki_v2` signature (after `skip_numeric_titles`):

```python
    skip_numeric_titles: bool = False,
    build_date: str = "1970-01-01",
) -> WikiResult:
```

3c. Capture the existing log BEFORE the clean step. Immediately after
`wiki_root = _wiki_dir(project_root, output_dir)` (line ~732), before the clean
loop, add:

```python
    prior_log = ""
    _log_path = wiki_root / "log.md"
    if _log_path.is_file():
        prior_log = _log_path.read_text(encoding="utf-8")
```

3d. After `_write_v2_indices(...)` (line ~766) and before the `index.json`
serialization, add the catalog + log writes:

```python
    # index.md catalog (content-oriented) + append-only log.md
    catalog_rows = [
        (
            (cat_path[0] if cat_path else "_uncategorized"),
            topic.title,
            "/".join((*cat_path, topic.slug)) if cat_path else topic.slug,
            [ev.doc_id for ev in topic.evidence],
        )
        for topic, cat_path in zip(final_topics, final_paths, strict=True)
    ]
    _atomic_write_bytes(
        wiki_root / "index.md",
        serialize_markdown(render_index_md(catalog_rows)).encode("utf-8"),
    )
    pins_total = sum(e.pin_count for e in final_entries)
    new_line = render_log_entry(
        date=build_date, provider=provider_name,
        topics=len(final_topics), pins=pins_total,
    )
    log_text = (prior_log.rstrip("\n") + "\n" + new_line) if prior_log.strip() else new_line
    _atomic_write_bytes(
        wiki_root / "log.md",
        serialize_markdown(log_text).encode("utf-8"),
    )
```

3e. Confirm `serialize_markdown` is imported in `orchestrator.py`. If not, add:

```python
from ..serialization import serialize_markdown
```

(Check existing imports first - it may already be present.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_v2_catalog.py tests/test_wiki_v2_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Thread `build_date` from CLI (optional but required for real builds)**

Open `src/kb_extract/cli.py`, find the `wiki build` command that calls
`build_wiki_v2`. Add a `--build-date` option (default: today's date via
`datetime.date.today().isoformat()`, computed in the CLI layer only, NOT in the
library) and pass it through. Add a CLI test in `tests/test_requirements_cli.py`
style if a wiki-build CLI test file exists; otherwise verify manually in Task 16.

- [ ] **Step 6: Full gate + commit**

Run: `uv run pytest` then `uv run ruff check .`
Expected: all pass, ruff clean.

```bash
git add tests/test_wiki_v2_catalog.py src/kb_extract/wiki/orchestrator.py src/kb_extract/cli.py
git commit -m "feat(wiki): write index.md catalog and append-only log.md in v2 build" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

**End of F2-A.** PR if following per-phase PR workflow.

---

## PHASE F2-B: Entity/concept aggregation pages + wikilink verify

### Task 12: Deterministic candidate extraction

**Files:**
- Create: `src/kb_extract/wiki/entities.py`
- Test: `tests/test_wiki_entities.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_entities.py`:

```python
from kb_extract.wiki.entities import Candidate, extract_candidates


def test_extract_candidates_finds_cross_domain_doc_ids():
    # Two topics in different domains both cite doc M1041012 -> cross-domain.
    topics = [
        {"slug": "hinge", "title": "Hinge", "domain": "mechanical",
         "category_path": "bc/mechanical",
         "evidence_doc_ids": ["M1041012", "M1320722"]},
        {"slug": "battery", "title": "Battery", "domain": "electrical",
         "category_path": "bc/electrical",
         "evidence_doc_ids": ["M1041012"]},
        {"slug": "boot", "title": "Boot", "domain": "software",
         "category_path": "bc/software",
         "evidence_doc_ids": ["M9999999"]},
    ]
    cands = extract_candidates(topics, min_domains=2)
    by_key = {c.key: c for c in cands}
    # M1041012 spans mechanical + electrical -> candidate.
    assert "M1041012" in by_key
    assert sorted(by_key["M1041012"].domains) == ["electrical", "mechanical"]
    # M1320722 + M9999999 appear in only one domain -> excluded.
    assert "M1320722" not in by_key
    assert "M9999999" not in by_key
    # Backlinks sorted + deterministic.
    assert by_key["M1041012"].backlinks == sorted(by_key["M1041012"].backlinks)


def test_candidate_is_frozen_dataclass():
    c = Candidate(key="X", kind="entity", domains=("a", "b"),
                  backlinks=("bc/a/x", "bc/b/y"))
    assert c.key == "X"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_entities.py -v`
Expected: FAIL - module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `src/kb_extract/wiki/entities.py`:

```python
"""Cross-domain entity/concept aggregation for the Obsidian wiki layer.

Phase 1 (this module, deterministic): scan topic metadata for shared evidence
documents that span >= ``min_domains`` distinct domains. Each such shared doc
becomes an aggregation *candidate* with sorted backlinks to every topic that
cites it. Phase 2 (``build_aggregation_pages``) uses the cached LLM provider to
author a short synthesis per candidate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candidate:
    key: str               # the shared doc id (entity key)
    kind: str              # "entity" | "concept"
    domains: tuple[str, ...]
    backlinks: tuple[str, ...]   # category_path/slug for each citing topic


def extract_candidates(
    topics: list[dict], *, min_domains: int = 2
) -> list[Candidate]:
    """Return cross-domain aggregation candidates, sorted by key.

    ``topics`` items must carry: ``slug``, ``domain``, ``category_path``,
    ``evidence_doc_ids`` (list[str]).
    """
    domains_by_doc: dict[str, set[str]] = defaultdict(set)
    backlinks_by_doc: dict[str, set[str]] = defaultdict(set)
    for t in topics:
        link = f"{t['category_path']}/{t['slug']}"
        for doc_id in t.get("evidence_doc_ids", []):
            domains_by_doc[doc_id].add(t["domain"])
            backlinks_by_doc[doc_id].add(link)

    out: list[Candidate] = []
    for key in sorted(domains_by_doc):
        domains = domains_by_doc[key]
        if len(domains) < min_domains:
            continue
        out.append(Candidate(
            key=key,
            kind="entity",
            domains=tuple(sorted(domains)),
            backlinks=tuple(sorted(backlinks_by_doc[key])),
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_entities.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_entities.py src/kb_extract/wiki/entities.py
git commit -m "feat(wiki): extract cross-domain aggregation candidates" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 13: Render entity aggregation pages

**Files:**
- Modify: `src/kb_extract/wiki/entities.py`
- Test: `tests/test_wiki_entities.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_wiki_entities.py`:

```python
from kb_extract.wiki.entities import render_entity_page


class _Llm:
    name = "fake"

    def chat(self, messages):
        return "This document is shared across mechanical and electrical."


def test_render_entity_page_has_frontmatter_backlinks_and_summary():
    cand = Candidate(key="M1041012", kind="entity",
                     domains=("electrical", "mechanical"),
                     backlinks=("bc/electrical/battery", "bc/mechanical/hinge"))
    md = render_entity_page(cand, _Llm())
    assert md.startswith("---\n")
    assert "type: entity" in md
    assert "# M1041012" in md
    assert "## Appears in" in md
    # Backlinks rendered as wikilinks, sorted.
    assert "[[bc/electrical/battery|battery]]" in md
    assert md.index("battery") < md.index("hinge")
    assert "shared across mechanical and electrical" in md
    assert md.endswith("\n")
    assert "\r" not in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_entities.py::test_render_entity_page_has_frontmatter_backlinks_and_summary -v`
Expected: FAIL - `render_entity_page` not defined.

- [ ] **Step 3: Write minimal implementation**

Add to `src/kb_extract/wiki/entities.py` (imports at top, function at bottom):

```python
from .frontmatter import build_frontmatter, render_frontmatter
from .providers.base import LlmClient, Message
from .wikilink import to_wikilink
from ..serialization import serialize_markdown
```

```python
def _summary_messages(cand: Candidate) -> list[Message]:
    sys: Message = {
        "role": "system",
        "content": (
            "You are maintaining a cross-domain knowledge wiki. Write a short "
            "(2-4 sentence) synthesis describing what this shared source covers "
            "and why it connects the listed domains. Do not invent specifics; "
            "stay general if unsure. No markdown headings."
        ),
    }
    user: Message = {
        "role": "user",
        "content": (
            f"Shared source: {cand.key}\n"
            f"Connected domains: {', '.join(cand.domains)}\n"
            f"Referenced by topics: {', '.join(cand.backlinks)}"
        ),
    }
    return [sys, user]


def render_entity_page(cand: Candidate, llm: LlmClient) -> str:
    """Render one entity/concept aggregation page (frontmatter + summary +
    sorted wikilink backlinks)."""
    summary = llm.chat(_summary_messages(cand)).strip()
    fm = render_frontmatter(build_frontmatter(
        title=cand.key,
        category_path=(cand.kind,),  # entities/ or concepts/
        slug=cand.key,
        doc_ids=[cand.key],
        page_type=cand.kind,
        extra_tags=[f"domain/{d}" for d in cand.domains],
    ))
    lines = [
        fm.rstrip("\n"),
        "",
        f"# {cand.key}",
        "",
        summary,
        "",
        "## Appears in",
        "",
    ]
    for link in cand.backlinks:
        label = link.rsplit("/", 1)[-1]
        lines.append(f"- {to_wikilink(link, label)}")
    lines.append("")
    return serialize_markdown("\n".join(lines))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_entities.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_entities.py src/kb_extract/wiki/entities.py
git commit -m "feat(wiki): render cross-domain entity aggregation pages" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 14: Wire entity pages into `build_wiki_v2`

**Files:**
- Modify: `src/kb_extract/wiki/orchestrator.py` (after catalog writes in Task 11)
- Modify: `src/kb_extract/wiki/entities.py` (add `build_aggregation_pages`)
- Test: `tests/test_wiki_v2_entities.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_v2_entities.py` (mirror e2e fixture; needs a kb tree
where one doc is cited from two domains - the e2e fixture may already satisfy
this; if not, add a second domain citing a shared doc):

```python
from pathlib import Path

from kb_extract.wiki.orchestrator import build_wiki_v2


def test_build_writes_entity_pages_when_cross_domain(tmp_path: Path):
    # Build kb + taxonomy such that one doc id is cited in two domains.
    build_wiki_v2(tmp_path, taxonomy=..., provider="mock", output_dir=tmp_path,
                  build_date="2026-06-25")
    ent_dir = tmp_path / "wiki" / "entities"
    # When the fixture has a cross-domain shared doc, the folder exists with
    # at least one page; otherwise it is absent (no crash).
    if ent_dir.is_dir():
        pages = list(ent_dir.glob("*.md"))
        assert pages
        text = pages[0].read_text(encoding="utf-8")
        assert "## Appears in" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_v2_entities.py -v`
Expected: FAIL if fixture is cross-domain (no `entities/` written); otherwise
the conditional passes trivially - in that case STRENGTHEN the fixture to force
a cross-domain shared doc so the assertion runs.

- [ ] **Step 3: Write minimal implementation**

3a. Add `build_aggregation_pages` to `src/kb_extract/wiki/entities.py`:

```python
from pathlib import Path


def build_aggregation_pages(
    wiki_root: Path,
    topics_meta: list[dict],
    llm: LlmClient,
    *,
    min_domains: int = 2,
) -> int:
    """Write entity aggregation pages under ``wiki/entities/``.

    Returns the number of pages written. No-op (returns 0) when there are no
    cross-domain candidates.
    """
    cands = extract_candidates(topics_meta, min_domains=min_domains)
    if not cands:
        return 0
    ent_dir = wiki_root / "entities"
    ent_dir.mkdir(parents=True, exist_ok=True)
    for cand in cands:
        md = render_entity_page(cand, llm)
        (ent_dir / f"{cand.key}.md").write_bytes(md.encode("utf-8"))
    return len(cands)
```

3b. In `build_wiki_v2`, after the catalog/log writes (Task 11, step 3d), add:

```python
    topics_meta = [
        {
            "slug": topic.slug,
            "title": topic.title,
            "domain": cat_path[0] if cat_path else "_uncategorized",
            "category_path": "/".join(cat_path) if cat_path else "_uncategorized",
            "evidence_doc_ids": [ev.doc_id for ev in topic.evidence],
        }
        for topic, cat_path in zip(final_topics, final_paths, strict=True)
    ]
    build_aggregation_pages(wiki_root, topics_meta, llm)
```

3c. Add the import at top of `orchestrator.py`:

```python
from .entities import build_aggregation_pages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_v2_entities.py tests/test_wiki_v2_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wiki_v2_entities.py src/kb_extract/wiki/entities.py src/kb_extract/wiki/orchestrator.py
git commit -m "feat(wiki): generate entity aggregation pages during v2 build" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 15: `verify_wikilinks` dead-link check

**Files:**
- Modify: `src/kb_extract/wiki/orchestrator.py` (`verify_wiki` or a new helper)
- Test: `tests/test_wiki_wikilink_verify.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_wikilink_verify.py`:

```python
from pathlib import Path

from kb_extract.wiki.orchestrator import verify_wikilinks


def _page(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_verify_wikilinks_passes_when_targets_exist(tmp_path: Path):
    wiki = tmp_path / "wiki"
    _page(wiki / "a.md", "see [[b]]")
    _page(wiki / "b.md", "hello")
    assert verify_wikilinks(wiki) == []


def test_verify_wikilinks_flags_dead_link(tmp_path: Path):
    wiki = tmp_path / "wiki"
    _page(wiki / "a.md", "see [[missing-note]]")
    violations = verify_wikilinks(wiki)
    assert any("missing-note" in v for v in violations)


def test_verify_wikilinks_resolves_pathed_and_labeled(tmp_path: Path):
    wiki = tmp_path / "wiki"
    _page(wiki / "a.md", "see [[sys/sub/_index|Label]]")
    _page(wiki / "sys" / "sub" / "_index.md", "x")
    assert verify_wikilinks(wiki) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_wikilink_verify.py -v`
Expected: FAIL - `verify_wikilinks` not defined.

- [ ] **Step 3: Write minimal implementation**

Add to `src/kb_extract/wiki/orchestrator.py`:

```python
import re as _re

_WIKILINK_RE = _re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def verify_wikilinks(wiki_root: Path) -> list[str]:
    """Return a violation per ``[[target]]`` whose note file does not exist.

    Obsidian resolves a link by note name. We accept a match if any ``.md``
    file under ``wiki_root`` has either the exact relative path (``target.md``)
    or a basename equal to the link's final segment.
    """
    wiki_root = Path(wiki_root)
    if not wiki_root.is_dir():
        return []
    md_files = list(wiki_root.rglob("*.md"))
    rel_paths = {f.relative_to(wiki_root).with_suffix("").as_posix() for f in md_files}
    basenames = {f.stem for f in md_files}

    violations: list[str] = []
    for f in sorted(md_files):
        text = f.read_text(encoding="utf-8")
        for m in _WIKILINK_RE.finditer(text):
            target = m.group(1).strip()
            if target in rel_paths:
                continue
            if target.rsplit("/", 1)[-1] in basenames:
                continue
            rel = f.relative_to(wiki_root).as_posix()
            violations.append(f"{rel}: dead wikilink [[{target}]]")
    return sorted(violations)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_wikilink_verify.py -v`
Expected: PASS.

- [ ] **Step 5: Integrate into the CLI `wiki verify` path**

Open `src/kb_extract/cli.py`, find where `verify_wiki(...)` violations are
printed. Add a call to `verify_wikilinks(wiki_root)` and merge its violations
into the same output/exit-code path (an empty list keeps `wiki verify: ok`).
Reuse the existing `_wiki_dir(project_root, output_dir)` to locate the root.

- [ ] **Step 6: Full gate + commit**

Run: `uv run pytest` then `uv run ruff check .`
Expected: all pass, ruff clean.

```bash
git add tests/test_wiki_wikilink_verify.py src/kb_extract/wiki/orchestrator.py src/kb_extract/cli.py
git commit -m "feat(wiki): verify wikilinks resolve to existing notes" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

**End of F2-B.**

---

## PHASE FINAL: Rebuild demo + docs

### Task 16: Rebuild k-bur demo and update README (Chinese)

**Files:**
- Modify: `README.md`
- (Regenerate, not commit) local demo at `C:\Users\xumax\AI Project\Private\markdown\k-bur`

- [ ] **Step 1: Rebuild the demo wiki with the new format**

```powershell
cd "C:\Users\xumax\AI Project\kb-extract"; $env:PYTHONIOENCODING='utf-8'
$proj="C:\Users\xumax\AI Project\Private\markdown\k-bur"
uv run kb wiki build "$proj" -o "$proj" --provider cached --build-date 2026-06-25
```

Expected: build completes; `wiki/index.md`, `wiki/log.md`, frontmatter on pages,
`wiki/entities/` present.

- [ ] **Step 2: Verify both layers green**

```powershell
uv run kb verify "$proj" -o "$proj"
uv run kb wiki verify "$proj" -o "$proj"
```

Expected: `verify: ok=True ... violations=0` and `wiki verify: ok` (including the
new wikilink check). If wikilink violations appear, fix the offending generator
(usually a slug/path mismatch) before proceeding.

- [ ] **Step 3: Spot-check Obsidian compatibility**

Confirm a topic page begins with a `---` frontmatter block, an `_index.md` uses
`[[...]]` links, `index.md` lists pages grouped by domain, and at least one
`entities/*.md` page has an `## Appears in` backlink section.

- [ ] **Step 4: Update README.md (Chinese, user-facing)**

Add a section documenting the two new capabilities. Insert after the existing
wiki section (find it with a quick search for "wiki" in `README.md`). Use this
Chinese copy (no fancy unicode - plain `->`):

```markdown
## Requirements 精确溯源

每条抽取出的需求都附带一段经确定性校验的逐字源文引用(EvidenceQuote)。该引用
必须逐字出现在源 main.md 中,校验不通过则自动丢弃,绝不编造。requirements.md 中
以引用块形式展示,便于直接看到"这条需求来自哪句话"。

## Obsidian 兼容 wiki

`kb wiki build` 生成的 wiki 兼容 Obsidian:

- 每页带 YAML frontmatter(title / domain / category_path / tags / evidence_sources),
  可配合 Dataview 与 graph view 使用。
- 页面间导航使用 `[[wikilinks]]`;证据回链仍指向确定性的 kb 锚点。
- `index.md` 为内容目录(按 domain 分组),`log.md` 为追加式构建日志。
- `entities/` 下为跨 domain 聚合页:同一份被多个 domain 引用的源文档会生成一页,
  用 `## Appears in` 反链回所有引用它的 topic,在 graph view 中即可看到跨域关联。

`kb wiki verify` 额外校验所有 wikilink 均指向存在的页面,防止 Obsidian 死链。
```

- [ ] **Step 5: Final gate + commit**

Run: `uv run pytest` then `uv run ruff check .`
Expected: all pass, ruff clean.

```bash
git add README.md
git commit -m "docs: document precise requirement evidence and Obsidian wiki" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 6: Open PR**

Push the branch and open a PR to main summarizing F1 + F2-A + F2-B. Do not push
to main directly.

---

## Self-Review notes (addressed)

- **Spec coverage:** F1 (Tasks 1-4), F2-A frontmatter/wikilinks/index/log (Tasks
  5-11), F2-B entity pages + wikilink verify (Tasks 12-15), demo rebuild + README
  (Task 16). All spec sections map to tasks.
- **Determinism:** frontmatter fixed key order + sorted lists (Task 5); catalog
  sorted by domain/title (Task 10); `build_date` injected, not wall-clock (Tasks
  10-11); entity backlinks sorted (Tasks 12-13); all writes via
  `serialize_markdown`.
- **Verify safety:** confirmed `verify_wiki` ignores page bodies; frontmatter +
  wikilinks do not affect H14/H17/H18. New `verify_wikilinks` is additive.
- **Type consistency:** `build_frontmatter`/`render_frontmatter`,
  `to_wikilink(target, label)`, `Candidate(key, kind, domains, backlinks)`,
  `extract_candidates(topics, min_domains=)`, `render_entity_page(cand, llm)`,
  `build_aggregation_pages(wiki_root, topics_meta, llm, min_domains=)`,
  `render_index_md(rows)`, `render_log_entry(date=, provider=, topics=, pins=)`,
  `build_topic_markdown(..., frontmatter=)`, `build_wiki_v2(..., build_date=)`,
  `verify_wikilinks(wiki_root)` - names are consistent across tasks.
- **Fixture reuse:** F2 integration tests (Tasks 8, 9, 11, 14) explicitly say to
  copy the kb+taxonomy fixture from `tests/test_wiki_v2_e2e.py` rather than
  inventing taxonomy shapes - the implementer must read that file first.
