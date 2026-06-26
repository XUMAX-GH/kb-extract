# Design: Precise Requirement Evidence + Obsidian-Compatible Wiki

Date: 2026-06-25
Status: Approved (pending spec review)

## Problem

Two user-reported gaps in the enrichment layer (`src/kb_extract/wiki/`):

1. **Imprecise requirement traceability.** `requirements.md` links each requirement
   to a coarse section anchor (`[sec-0006](main.md#sec-0006)`). A `main.md` of
   2830 lines has only ~10 `sec-NNNN` anchors (roughly one per page/major
   section). Clicking a link lands on the top of a whole page, so the reader
   cannot see *which sentence* a summarized requirement was derived from. The
   user needs to know the exact source passage behind each requirement.

2. **Wiki is not Obsidian-native and lacks cross-domain associations.** The user
   will manage the wiki in Obsidian and wants to discover how the same knowledge
   (a part, a concept) connects *across* domains. The current wiki uses
   deterministic footnote citations and Chinese hierarchical index pages, but has
   no `[[wikilinks]]`, no YAML frontmatter (for Dataview/graph), no `index.md` /
   `log.md`, and no entity/concept aggregation pages. The user wants the final
   wiki output to follow the Karpathy "persistent, compounding wiki" concept
   (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Constraints (AGENTS.md hardness)

- Adapters (`src/kb_extract/adapters/`) must never import LLM SDKs. Both features
  live entirely in the wiki enrichment layer; the deterministic core
  (`kb/main.md` + `sec-NNNN` anchors) is the citable evidence substrate and is
  NOT modified.
- Tests run with `--disable-socket`; provider calls in tests use cached/fake
  providers.
- Output must be byte-identical across platforms (H13): fixed field ordering,
  sorted tags/links, LF newlines, `serialize_markdown` normalization on every
  write.
- English code/tests/docstrings/commits; Chinese user-facing doc copy.
- Verify must stay green: `uv run kb verify` and `uv run kb wiki verify`.

## Scope decisions (from brainstorming)

- F1 approach: attach a deterministically-verified verbatim quote to each
  requirement (NOT finer `main.md` anchors).
- F2 form: evolve the existing `kb wiki build` output into Obsidian-compatible
  format (single artifact), NOT a separate export command.
- F2 cross-domain depth: option C, in two phases - (A) deterministic
  tags/backlinks skeleton, then (B) LLM-authored entity/concept aggregation pages.

---

## Feature 1: Precise requirement evidence

### Data model

`wiki/requirements/models.py::TestItem` gains one field:

- `evidence_quote: str` - a verbatim excerpt from the source section body that
  the requirement is derived from. Empty string when no verifiable quote is
  available.

`to_dict()` adds `"EvidenceQuote"`. `sort_key()` is unchanged (still keyed by
evidence_ref, category, function, what) so ordering stays deterministic.

### Prompt

`wiki/requirements/prompts.py` is updated to ask the model to also return an
`EvidenceQuote` field per item: the single sentence or table row (verbatim, copied
exactly from the provided section text) that most directly supports the
requirement. The prompt instructs: copy text exactly, do not paraphrase, keep it
short (one sentence / one row).

### Deterministic verification (zero-hallucination guard)

`wiki/requirements/models.py::coerce_item` verifies the quote before accepting it:

1. Normalize whitespace in both the candidate quote and the section body
   (collapse runs of whitespace to a single space, strip). Keep a mapping from
   the normalized body back to the original so the rendered quote uses original
   text.
2. If the normalized quote is a non-empty substring of the normalized body,
   accept it and store the matched **original** substring as `evidence_quote`.
3. Otherwise set `evidence_quote = ""` (drop it). Never fabricate or
   approximate - an unverifiable quote is silently omitted.

This keeps the zero-hallucination property: only text that literally exists in
the source is ever shown.

A new helper `find_verbatim(quote, body) -> str | None` encapsulates the
normalization + substring match and is unit-tested independently.

### Rendering

`wiki/requirements/render.py::render_markdown` renders the quote as a blockquote
directly under each requirement, so the reader sees the exact source sentence
without leaving the page. The section anchor link is retained for navigation:

```
- **<Function>** ([sec-0006](main.md#sec-0006))
  - What: ...
  - How: ...
  - Sample Size: ...
  - Source: <doc> / <section>
  - Evidence: > "<verbatim quote>"
```

When `evidence_quote` is empty the Evidence line is omitted (no empty blockquote).
`render_json` includes `EvidenceQuote` for completeness.

### Edge cases

- Quote spans a chunk boundary: only the chunk fed to the model is searched;
  if the model returns text not in that chunk, it is dropped (correct - we cannot
  verify across chunks).
- Quote contains markdown table pipes / special chars: substring match is on
  normalized plain text; rendering escapes nothing (blockquote of raw source is
  acceptable and matches faithful-extraction intent).
- Backward compatibility: existing `requirements.json` consumers see a new
  `EvidenceQuote` key; existing keys unchanged.

---

## Feature 2: Obsidian-compatible wiki

### Phase A - deterministic skeleton (no extra LLM calls)

All derived from existing topic metadata in `wiki/index.json`; fully reproducible.

**A1. YAML frontmatter** on every generated wiki page. Fixed key order:

```yaml
---
title: <topic title>
domain: <top-level category slug>
category_path: <full slug path, e.g. bc/mechanical>
slug: <slug>
evidence_sources: [<doc_id>, ...]   # sorted, unique
tags: [domain/<domain>, <category-path-derived tags...>]   # sorted, unique
---
```

A small module `wiki/frontmatter.py` builds and serializes frontmatter
deterministically (sorted lists, stable key order, LF). Topic-page and
index-page writers prepend it.

**A2. `[[wikilinks]]`** for inter-wiki navigation (subcategory lists, "related
articles" lists, index entries) replace relative `.md` links. Obsidian resolves
wikilinks by note name; a helper `wiki/wikilink.py::to_wikilink(target, label)`
centralizes formatting (`[[target|label]]`). Evidence citations stay as the
existing footnote + `sec-NNNN` anchor links (so `wiki verify` is unaffected and
evidence remains precisely anchored).

**A3. `index.md`** (content catalog): one line per page with a one-sentence
summary, grouped by domain. Regenerated every build; deterministic ordering.

**A4. `log.md`** (append-only chronological): each build appends
`## [YYYY-MM-DD] build | <provider>, topics=N, pins=M`. To preserve byte
reproducibility in tests, the date is injected (not read from the clock) via an
existing/added build timestamp parameter; tests pass a fixed date.

### Phase B - LLM entity/concept aggregation pages

**B1. Candidate extraction.** A deterministic pre-pass scans topic pages for
recurring entities/concepts (driven by taxonomy + repeated capitalized
part/document tokens and concept terms), producing a candidate list. The LLM is
then asked (via the existing cached provider) to confirm/name each
entity/concept and write a short synthesis.

**B2. Pages.** Generated under `wiki/entities/<slug>.md` and
`wiki/concepts/<slug>.md`, each with frontmatter (`type: entity|concept`,
`tags`), a short LLM-authored summary, and a `## Appears in` section of
`[[backlinks]]` to every topic/domain that mentions it (sorted, deterministic).

**B3. Graph.** Obsidian's graph view + Dataview surface the cross-domain
associations from these pages' backlinks and the shared tags.

### Verification

- `wiki verify` reads `index.json` and checks topic `.md` existence + kb anchor
  validity (H14/H17/H18). It does NOT parse page bodies, so frontmatter and
  wikilinks do not affect it. Confirmed by reading
  `orchestrator.py::verify_wiki`.
- New lightweight check: a `verify_wikilinks` pass ensures every `[[target]]`
  emitted by the build resolves to an existing wiki note (prevents Obsidian dead
  links). Reported as wiki violations alongside the existing checks.

### Determinism

- Frontmatter: fixed key order, sorted list values.
- Tags / wikilinks / backlinks: sorted, de-duplicated.
- `log.md`: injected date, not wall clock.
- Entity/concept LLM content: via cached provider, same as existing topic
  authoring, so demo rebuilds are reproducible.
- All writes go through `serialize_markdown`.

---

## Testing strategy (TDD)

Each task: write failing test, implement, commit together (one TDD task per
commit, English message, no fancy unicode).

- F1: `find_verbatim` (match / normalized match / no-match -> drop); `coerce_item`
  populates/drops `evidence_quote`; `render_markdown` emits/omits the blockquote;
  `render_json` includes the key.
- F2-A: `frontmatter.py` field order + sorting; `to_wikilink` formatting;
  `index.md` grouping/ordering; `log.md` append format with injected date;
  topic-page writer prepends frontmatter and uses wikilinks; `wiki verify` still
  green on a fixture.
- F2-B: candidate extraction determinism; entity/concept page structure; backlink
  sorting; `verify_wikilinks` catches a dead link.

Gate (must pass before any completion claim): `uv run pytest` and
`uv run ruff check .`.

## Rollout

1. F1 (small, self-contained) - PR.
2. F2 Phase A (frontmatter, wikilinks, index/log) - PR.
3. F2 Phase B (entity/concept pages, wikilink verify) - PR.
4. Rebuild the k-bur demo wiki with the new format; confirm `kb verify` and
   `kb wiki verify` both `ok`. Update README (Chinese, per repo convention).

## Out of scope

- Changing `main.md` anchors or any deterministic-core output.
- Embedding-based search (Karpathy notes the index file suffices at this scale).
- Replacing the existing footnote evidence mechanism (kept as the precise,
  verifiable anchor backbone underneath the Obsidian layer).
