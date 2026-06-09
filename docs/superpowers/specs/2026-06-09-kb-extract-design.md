# `kb-extract` — Design Spec (v1)

**Status**: Draft for user review
**Date**: 2026-06-09
**Scope**: Sub-project #1 (Extraction pipeline) of the larger personal-KB system
**Out of scope (this spec)**: PageIndex tree refinement, Wiki organization layer, Memory layer, GitHub auto-publish workflow — each gets its own future spec.

---

## 1. Problem & goals

The user (Microsoft Surface engineer) keeps per-project working directories under `C:\Users\xumax\AI Project\Private\<project>\` containing engineering documents in PDF, DOCX, XLSX, PPTX, standalone images, and ZIP archives. They want every project folder to become an independent, structured Markdown knowledge base that downstream layers (PageIndex-style indexing, Karpathy-LLM-Wiki-style organization, hardness-rigorous evidence linking, memory) can build on.

This spec covers only the lowest layer: **extracting source documents into deterministic, citable Markdown**.

### Goals

- Convert PDF / DOCX / XLSX / PPTX / standalone PNG-JPG / ZIP (recursive) to Markdown.
- Preserve images into a per-document `assets/` subdir; reference them from Markdown via relative links.
- Emit a PageIndex-style recursive section tree as a sidecar `index.json` per document.
- Mark every paragraph with a stable invisible anchor so downstream layers can cite an exact span.
- Be **provably deterministic** and **provably hallucination-free**: no LLM is invoked during extraction; output is byte-identical across re-runs and across platforms; every invariant is machine-checkable.
- Be invokable both as a standalone CLI (`kb extract <path>`) and as a Copilot CLI skill (for VS Code integrated terminal use).

### Hard constraints (from user)

- All extraction code runs locally; document content never leaves the machine during extraction.
- LLMs are permitted only in higher layers (PageIndex refinement, Wiki organization, etc.) and only via GitHub Copilot's bundled models, which are already provisioned for Microsoft employees.
- The system must satisfy a "hardness/harness" rigor bar: every extracted unit traceable to source, every invariant explicitly checkable, no silent failures.

### Non-goals for v1

| Non-goal | Deferred to |
|---|---|
| LLM-assisted section-tree refinement | Sub-project #2 (PageIndex layer) |
| Cross-document wiki / reverse-link / knowledge condensation | Sub-project #3 (Wiki layer) |
| OCR of scanned PDFs | Sub-project #1.5 |
| STP CAD metadata extraction | Sub-project #1.6 |
| Visio `.vsdx` / legacy `.doc` | Sub-project #1.7 |
| User memory / question history | Sub-project #5 |
| GitHub auto-publish workflow | Sub-project #6 |
| Multi-project concurrency | Not planned (would jeopardise byte-identical determinism) |
| Cross-document asset deduplication | Sub-project #3 |
| Incremental per-page PDF re-extraction | Not planned |
| **Any LLM call inside the extraction layer** | **Never** (root of hardness invariant H2) |
| **Modifying source files** | **Never** (source is read-only) |

---

## 2. Inputs & outputs

### 2.1 Supported inputs (Tier 2)

| Extension | Handler | Notes |
|---|---|---|
| `.pdf` | `pdf_docling` | Layout-transformer based; uses `docling` (IBM, fully local) |
| `.docx` | `docx` | `python-docx` |
| `.xlsx` | `xlsx` | `openpyxl` (read_only, data_only) |
| `.pptx` | `pptx` | `python-pptx` |
| `.png`, `.jpg`, `.jpeg` | `image` | Pillow; one section per image |
| `.zip` | `zip` | Unpack to tmp, recurse into orchestrator |

Detection uses extension + libmagic byte signatures to defeat trivial renames.

### 2.2 Per-document output layout

For a source file `BUR-K/M9000018-DOC_MP44_MAIN-REV_E.pdf`, the orchestrator writes:

```
BUR-K/kb/M9000018-DOC_MP44_MAIN-REV_E/
├── main.md            UTF-8 (no BOM), LF line endings, single trailing newline
├── index.json         Serialized SectionNode tree; sort_keys, indent=2, LF, UTF-8 (no ASCII escape)
├── meta.json          Serialized ExtractionMeta
└── assets/
    ├── p3-img1.png
    ├── p3-img2.png
    └── p17-table1.png
```

Source files are never moved or modified.

### 2.3 Per-project layout

```
BUR-K/
├── <original source files, untouched>
└── kb/
    ├── manifest.sqlite       Per-project total index of extracted documents
    ├── M9000018-DOC_MP44_MAIN-REV_E/
    └── <other documents>/
```

`kb/` is the only place the tool writes inside the project root.

---

## 3. Architecture overview

Pipeline + adapters.

```
                   ┌──────────────────────┐
   user CLI ──────►│   orchestrator       │
   skill scripts   │  (discover, schedule,│
                   │   verify, persist)   │
                   └────────┬─────────────┘
                            │ Extractor protocol
            ┌───────────────┼────────────────┐
            ▼               ▼                ▼
    ┌──────────────┐  ┌───────────┐  ┌───────────┐
    │ pdf_docling  │  │  docx     │  │   pptx    │  …
    └──────────────┘  └───────────┘  └───────────┘
            │               │                │
            └───────────────┴────────────────┘
                            │
                            ▼
                  ExtractionResult contract
                   (markdown + index + assets + meta)
                            │
                            ▼
                  hardness.assert_invariants
                            │
                            ▼
                  write atomically to disk
```

### 3.1 Repository layout

```
kb-extract/
├── pyproject.toml
├── README.md
├── install.ps1 / install.sh
├── uninstall.ps1 / uninstall.sh
├── src/kb_extract/
│   ├── __init__.py
│   ├── cli.py                       # `kb` console-script
│   ├── orchestrator.py
│   ├── contracts.py                 # frozen, slotted dataclasses (shared contract)
│   ├── hardness.py                  # pure invariant checkers
│   ├── layout.py                    # target_dir / project_root resolution
│   ├── manifest.py                  # SQLite manifest reader/writer
│   └── adapters/
│       ├── __init__.py
│       ├── base.py                  # Extractor Protocol + registry
│       ├── pdf_docling.py
│       ├── docx.py
│       ├── xlsx.py
│       ├── pptx.py
│       ├── image.py
│       └── zip.py
├── tests/
│   ├── fixtures/                    # tiny public-domain inputs
│   ├── golden/                      # syrupy snapshots
│   ├── test_contracts.py
│   ├── test_hardness.py
│   ├── test_orchestrator.py
│   ├── test_no_llm_imports.py       # static AST scan for H2
│   ├── test_cross_platform.py       # H13
│   ├── test_e2e.py
│   ├── test_performance.py          # CI hard gate (1.5x baseline)
│   └── adapters/test_<format>.py
├── skill/
│   ├── SKILL.md                     # skill metadata
│   └── scripts/
│       ├── extract.ps1
│       ├── extract.sh
│       ├── verify.ps1
│       └── verify.sh
├── .github/workflows/
│   └── ci.yml                       # matrix: {ubuntu, windows, macos} x {py3.11, py3.12}
├── .vscode/
│   └── tasks.json.example
└── docs/
    ├── superpowers/specs/2026-06-09-kb-extract-design.md  (this file)
    └── extraction-result-contract.md                       (public contract doc)
```

### 3.2 Module boundaries (do not break)

- `adapters/*` are used **only** via `base.Extractor` protocol. Orchestrator never imports a concrete adapter module by name.
- `contracts.py` types are `frozen=True, slots=True`. Shared with downstream sub-projects unchanged.
- `hardness.py` is pure: input is `ExtractionResult + source_path`, output is `None` (pass) or raises `HardnessViolation`. Never mutates.
- Skill scripts never import `kb_extract`. They shell out to the `kb` CLI and parse `--json` output. The skill→CLI process boundary is intentional and load-bearing.

---

## 4. Core contract: `ExtractionResult`

```python
# src/kb_extract/contracts.py
from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True, slots=True)
class SectionNode:
    """PageIndex-style recursive section node.

    Each leaf corresponds to a contiguous span of main.md and carries an `anchor`
    that exists exactly once in main.md as a `<a id="...">` invisible marker.
    Non-leaf nodes have anchor == "" and aggregate their children.
    """
    node_id: str            # e.g. "0001", "0001.0002"; doc-globally unique, sortable
    title: str              # heading text; for unnamed leaves, first 60 chars of body
    level: int              # 0 = root, 1 = chapter, 2 = section, ...
    page_start: int         # 1-based inclusive (or slide#/sheet-ordinal for non-PDF)
    page_end: int           # 1-based inclusive
    anchor: str             # leaf only; "" for non-leaf
    language: str           # langdetect ISO-639-1; "und" if undetermined
    children: tuple["SectionNode", ...] = ()

@dataclass(frozen=True, slots=True)
class TableRef:
    """A table extracted with its raw structured data, not just a markdown rendering."""
    anchor: str                            # e.g. "tbl-0001"
    page: int
    rows_json: tuple[tuple[str, ...], ...] # rectangular grid of cell strings
    rendered_asset: str | None             # rel path to PNG render in assets/, if any

@dataclass(frozen=True, slots=True)
class AssetRef:
    kind: Literal["image", "table_image", "embedded_file"]
    rel_path: str                          # e.g. "assets/p3-img1.png"
    page: int
    sha256: str
    width: int | None = None
    height: int | None = None
    alt: str = ""

@dataclass(frozen=True, slots=True)
class ExtractionMeta:
    source_path: str                       # relative to project root
    source_sha256: str
    source_bytes: int
    source_mtime_iso: str
    adapter_name: str                      # e.g. "pdf_docling"
    adapter_version: str                   # short code hash of adapter module
    tool_versions: dict[str, str]          # frozen at import time
    extracted_at_iso: str
    outline_source: Literal["bookmark", "heading_style", "docling_layout", "page_fallback"]
    status: Literal["ok", "partial", "failed"]
    warnings: tuple[str, ...] = ()         # each entry matches a registered regex pattern
    skipped_reasons: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class ExtractionResult:
    markdown: str                          # full main.md text including invisible anchors
    index: SectionNode                     # root of section tree
    tables: tuple[TableRef, ...]
    assets: tuple[AssetRef, ...]
    meta: ExtractionMeta

    def content_sha256(self) -> str:
        """sha256 over (markdown bytes || sorted asset sha256s || index.json bytes).

        Used for idempotency and verification.
        """
```

### 4.1 Markdown shape

Each adapter produces Markdown matching this shape:

```markdown
<!-- generated by kb-extract; do not edit; source_sha256: <hex> -->

<a id="sec-0001"></a>
# 1. Chapter Title

<a id="sec-0001-0001"></a>
## 1.1 Section Title

<a id="sec-0001-0001-0001"></a>
Paragraph body text...

![p3-img1](assets/p3-img1.png "alt from source")

<a id="tbl-0001"></a>
| col A | col B |
|---|---|
| ... | ... |
```

### 4.2 Determinism rules

- All file names sorted in UTF-8 byte order.
- JSON written with `sort_keys=True, ensure_ascii=False, indent=2, separators=(",", ": ")` and a trailing `\n`.
- Markdown is UTF-8 no BOM, LF line endings, exactly one trailing newline.
- Images written from raw byte streams from the source PDF/PPTX (no re-encoding); filenames use stable `p{page}-img{n}.{ext}` / `slide{n}-img{m}.{ext}` schemes.
- Dependency versions are pinned at minor in `pyproject.toml`; an upgrade bumps `adapter_version` and invalidates idempotency cache (intentional).

---

## 5. Orchestrator behavior

### 5.1 Main flow

```python
def run(path: Path, *, force: bool = False, dry_run: bool = False) -> RunReport:
    sources = discover_sources(path)          # 1
    project_root = find_project_root(path)    # 2
    manifest = open_manifest(project_root / "kb" / "manifest.sqlite")

    for src in sources:                        # 3
        adapter = registry.pick(src)           # 4  ext + libmagic
        if not adapter:
            manifest.mark_skipped(src, "no_adapter")
            continue

        src_hash = sha256_file(src)
        prev = manifest.get(src)
        if prev and prev.source_sha256 == src_hash and not force:   # 5 idempotent short-circuit
            continue

        out_dir = layout.target_dir(project_root, src)              # 6
        if dry_run:
            report.queue(src, action="would_extract")
            continue

        out_dir_tmp = out_dir.with_suffix(".tmp")
        out_dir_tmp.mkdir(parents=True, exist_ok=True)

        try:
            result = adapter.extract(src, out_dir_tmp)              # 7
        except Exception as e:                                       # 8
            manifest.mark_failed(src, repr(e))
            shutil.rmtree(out_dir_tmp, ignore_errors=True)
            continue

        hardness.assert_invariants(result, src)                     # 9
        write_result_to_disk(result, out_dir_tmp)                   # 10
        atomic_replace(out_dir_tmp, out_dir)                         # 11
        manifest.upsert(src, result.meta, output_sha256=...)         # 12

    manifest.flush()
    return report
```

### 5.2 Discovery rules

- `kb extract <root>` where the root contains multiple subdirs and no `kb/` itself → treat each immediate subdir as an independent project; run sequentially per project, each with its own manifest.
- `kb extract <project-dir>` → single-project mode.
- `kb extract <single-file>` → walk up to find nearest ancestor with `kb/` or use file's directory.
- Always skip: `kb/`, `.git/`, `*.tmp`, anything matching `.gitignore`.

### 5.3 ZIP handling

- Unpack to `out_dir_tmp/_unpacked/`.
- Recurse into orchestrator on `_unpacked/`.
- Inner artifacts land at `out_dir/<inner>/main.md`. The ZIP's own SectionNode aggregates children with `node_id` prefixes to avoid collisions.
- Nesting depth limit: 5. Beyond → `status=failed`, reason `zip_too_nested`.
- Encrypted zip → skipped with reason `zip_encrypted`.

### 5.4 Atomicity

- Adapter writes to `out_dir.tmp/`. On hardness failure, the tmp dir is discarded.
- Successful writes are atomically renamed to final location.
- Manifest writes use `manifest.sqlite` with WAL mode + transactions; partial writes are impossible.
- The user can `ctrl+C` at any moment and the on-disk state remains consistent.

---

## 6. Per-adapter spec

| Adapter | Engine | Section-tree source | Tables | Images | Example warnings |
|---|---|---|---|---|---|
| `pdf_docling` | docling + pymupdf | bookmark → docling layout heading → page fallback (recorded in `meta.outline_source`) | docling `Table` → markdown table + `tables[i].rows_json` + rendered PNG | docling figure regions + pymupdf embedded images, sorted by page; filename `p{page}-img{n}.{ext}` | `pdf.scanned_no_text_layer`, `pdf.password_protected`, `pdf.low_confidence_heading` |
| `docx` | python-docx | Heading 1/2/3 styles → tree directly | Word tables → markdown + rows_json | inline shapes + embedded images | `docx.unknown_style`, `docx.embedded_ole_skipped` |
| `xlsx` | openpyxl (read_only, data_only) | sheet name = level-1; block-of-contiguous-cells = level-2 | each block as TableRef with rows_json + 50-row markdown preview | sheet-embedded images via openpyxl-image-loader | `xlsx.formula_empty_cache`, `xlsx.merged_cells_flattened` |
| `pptx` | python-pptx | each slide = level-1 (title); shape table → leaf | shape tables → markdown + rows_json | picture shapes, z-order sorted | `pptx.animation_ignored`; speaker notes become `> Note:` block within the slide section |
| `image` | Pillow + EXIF reader | single root section, title = filename | — | the image itself, hashed + copied | EXIF stored as `image.exif:<tag>=<value>` warnings |
| `zip` | stdlib zipfile + recursion | aggregator only; no own structure | aggregated from children | aggregated from children | `zip.encrypted`, `zip.too_nested` |

Universal constraints on every adapter:
- Must not perform network I/O. Enforced by `pytest-socket` in tests.
- Must not import any LLM SDK. Enforced by H2 static scan.
- May only write within `out_dir_tmp/`. Orchestrator owns final placement.
- `warnings` entries must match a regex from the registered allowlist in `hardness.py`; freeform warnings are rejected by H11.

---

## 7. Hardness invariants

Each invariant is implemented as a pure function in `src/kb_extract/hardness.py`. Violation raises `HardnessViolation(invariant=H#, detail=...)`. The orchestrator catches it before any file in `out_dir` is written.

| ID | Invariant | Check | Why |
|---|---|---|---|
| H1 | Adapters perform no network I/O | runtime: tests run with `pytest-socket` denying sockets in adapter modules; CI enforces | extraction must not leak or hallucinate |
| H2 | Adapters import no LLM SDK | static: AST scan of `src/kb_extract/adapters/**` against a denylist (`openai`, `anthropic`, `litellm`, `langchain*`, `google.generativeai`, ...) in `tests/test_no_llm_imports.py` | compile-time hallucination wall |
| H3 | Anchor uniqueness | parse markdown, collect all `<a id="X">`, set size equals occurrence count | duplicate anchors corrupt downstream citations |
| H4 | Anchor completeness | every leaf `SectionNode.anchor` is present in markdown | the section tree and prose must agree |
| H5 | Asset closure | every `![](assets/X)` reference is in `result.assets` and exists on disk; conversely, every file in `assets/` is referenced | no missing pictures, no orphans |
| H6 | Asset hash truthfulness | each `AssetRef.sha256` recomputed must match | adapter can't lie about asset contents |
| H7 | Source hash truthfulness | `meta.source_sha256` recomputed must match | idempotency basis |
| H8 | Determinism | "double extract" test mode: run adapter twice on same input → `markdown`, `index.json`, `assets/*` byte-identical | actually idempotent, not just looks-like |
| H9 | Page-range closure | union of leaf `[page_start, page_end]` covers `[1, total_pages]` with no gaps and no overlaps | no missing pages |
| H10 | Outline-source truthfulness | when `outline_source ∈ {bookmark, heading_style}`, at least one node must be derived from that source (cross-checked against parser state) | adapters can't claim sophisticated sourcing they didn't use |
| H11 | Warnings allowlist | each warning matches a regex from a registered set | warnings remain machine-consumable by downstream layers |
| H12 | No silent skip | every non-`kb/` non-`.git/` source file in scope has a manifest row (any status) | discovery is exhaustive |
| H13 | Cross-platform identity | CI matrix produces identical output `sha256` on Ubuntu, Windows, macOS | true reproducibility |

`kb verify <project>` re-runs H3..H13 against artifacts already on disk (without re-extracting) and additionally checks that `main.md` on disk still hashes to the value recorded in the manifest — catching unauthorized manual edits.

---

## 8. CLI & Copilot skill

### 8.1 CLI

```
kb extract <path> [--force] [--dry-run] [--json] [--only ext[,ext]] [--adapter name]
kb verify <path>  [--json] [--fail-fast]
kb manifest <path> [--status ok|partial|failed|skipped] [--format table|json|csv]
kb adapters
kb --version
```

Exit codes: `0` ok, `1` at least one failed/partial, `2` usage error, `3` hardness violation (verify mode).

### 8.2 Copilot CLI skill

Layout under `skill/`:

```
SKILL.md           name, description, trigger phrases
scripts/
  extract.ps1      Windows
  extract.sh       *nix
  verify.ps1
  verify.sh
```

Contract written into `SKILL.md`:

1. The skill never parses documents itself; it only decides what subcommand and path to invoke.
2. The skill never modifies `main.md`, `index.json`, or `meta.json`; changes require `kb extract --force`.
3. The skill calls `kb adapters` before any extract command to confirm CLI availability; otherwise instructs the user to run `install.ps1` / `install.sh` from the repo root.
4. The skill summarises the CLI's `--json` output to the user but never enriches or paraphrases extracted content.

### 8.3 Installation

- `install.ps1` / `install.sh`:
  1. Create user venv at `~/.kb-extract/venv/`.
  2. `pip install -e .` from the repo.
  3. Trigger docling first-time model download (~500 MB) with progress shown.
  4. Add `kb` console_script to PATH (per-OS instructions, with idempotent edits to user profile).
- `uninstall.*` reverses the above.

### 8.4 VS Code integration (thin)

- The Copilot CLI skill is already callable from VS Code's integrated terminal — no extension authored.
- Ship `.vscode/tasks.json.example` so users can right-click → Run Task for "KB: Extract current folder" / "KB: Verify project".

---

## 9. Testing strategy

| Layer | Lives in | Purpose |
|---|---|---|
| Contract / unit | `tests/test_contracts.py`, `tests/adapters/test_<fmt>.py` | dataclass roundtrip; adapter-on-fixture smoke |
| Hardness | `tests/test_hardness.py` | each of H1..H13 has a good case (passes) and a bad case (raises) |
| Static no-LLM scan | `tests/test_no_llm_imports.py` | implements H2 |
| Golden | `tests/golden/` via `syrupy` | full extraction snapshot per format |
| E2E | `tests/test_e2e.py` | mini project with PDF + DOCX + XLSX + ZIP(PPTX) + standalone PNG; asserts manifest correctness, full `kb verify` pass, second-run zero-write idempotency |
| Cross-platform | `.github/workflows/ci.yml` matrix `{ubuntu, windows, macos} × {py3.11, py3.12}` plus a dedicated H13 hash-compare job that downloads artifacts from all three OS runs and compares sha256 manifests |
| Performance | `tests/test_performance.py` | 100-page PDF baseline, CI hard gate at 1.5× regression |

Test fixtures must contain only publicly licensed material; `tests/fixtures/SOURCES.md` documents provenance. No Microsoft confidential document is ever committed.

---

## 10. Risks & open issues

| Risk | Likelihood | Mitigation |
|---|---|---|
| docling not bit-identical across CPU vendors (AVX paths) | medium | force single-threaded inference, set `PYTHONHASHSEED=0`, pin `torch` to CPU-only build; if still flaky, relax H8/H13 to "structural equality after canonicalization" with explicit doc |
| docling first-time model pull blocked on user's network | low | document offline-install path: pre-download model bundle, set `DOCLING_ARTIFACTS_PATH` |
| `python-magic` requires libmagic native lib on Windows | medium | install script bundles `python-magic-bin` for Windows; runtime check at `kb adapters` |
| Engineering PDFs with embedded fonts that pymupdf can't decode | medium | adapter emits `pdf.font_decode_failed:<page>` warning and falls back to raw text-layer extraction for that page |
| 170 MB ZIP containing 100 MB STP files | confirmed | STP has no adapter in v1 → marked skipped with reason `no_adapter`; ZIP itself extracts other inner docs normally |

---

## 11. Future roadmap (out of this spec)

- Sub-project #2: PageIndex LLM-assisted section refinement on top of `pdf_docling` output for ill-structured PDFs.
- Sub-project #3: Karpathy LLM-Wiki + Obsidian-wiki organization layer; every wiki claim cites one or more `<anchor>` from extracted Markdown.
- Sub-project #4: Hardness extensions for the wiki layer (claim-must-cite, claim-must-be-supported-by-quoted-span).
- Sub-project #5: Memory layer for user habits and question history.
- Sub-project #6: GitHub auto-publish workflow to the user's `XUMAX-GH`-account repository (account to be confirmed before publish — currently authenticated as `xumax_microsoft`).
- Sub-project #1.5/.6/.7: OCR / STP / Visio adapter additions.

---

## 12. Acceptance criteria for v1 implementation

1. `kb extract C:\Users\xumax\AI Project\Private\BUR-K` produces `BUR-K\kb\M9000018-DOC_MP44_MAIN-REV_E\` with `main.md`, `index.json`, `meta.json`, populated `assets/`, all H3..H12 satisfied.
2. Running it again is a no-op (zero new bytes written; manifest row unchanged).
3. `kb verify C:\Users\xumax\AI Project\Private\BUR-K` exits 0.
4. Editing any byte of `main.md` and re-running `kb verify` exits 3 with a specific message naming the document.
5. CI matrix is green on all three OSes including the H13 cross-platform hash-compare job.
6. The Copilot CLI skill in `skill/` triggers on natural-language requests like "extract this folder" and successfully delegates to `kb extract --json`.
7. The static no-LLM-imports test (H2) is part of CI and fails when an LLM SDK import is introduced in any adapter.
