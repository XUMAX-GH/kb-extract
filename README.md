# kb-extract

Personal knowledge-base extraction pipeline. Converts PDF / DOCX / XLSX / PPTX /
PNG-JPG / ZIP into deterministic, citable Markdown with PageIndex-style sidecar
section trees and a per-document `assets/` folder.

**Status**: design phase. See [docs/superpowers/specs/2026-06-09-kb-extract-design.md](docs/superpowers/specs/2026-06-09-kb-extract-design.md).

## Hard constraints

- 100% local extraction. No network calls, no LLM SDKs anywhere in the extraction
  layer. Enforced by static import scan (H2) and `pytest-socket` (H1).
- Byte-identical re-runs across re-extractions and across OSes (H8, H13).
- Every paragraph carries an invisible `<a id="...">` anchor; every anchor is
  referenced exactly once by the sidecar `index.json` (H3, H4).
- `kb verify` re-checks every invariant on already-written artifacts without
  re-extracting.

## Architecture (v1)

```
kb extract <path> ──► orchestrator ──► Extractor (per-format adapter)
                                              │
                                              ▼
                              ExtractionResult contract
                                              │
                                              ▼
                              hardness.assert_invariants
                                              │
                                              ▼
                              atomic write to project/kb/<doc>/
```

## Layout

```
<project>/<source-file>            (untouched)
<project>/kb/manifest.sqlite       per-project index
<project>/kb/<doc>/main.md         Markdown with invisible anchors
<project>/kb/<doc>/index.json      PageIndex-style section tree
<project>/kb/<doc>/meta.json       provenance + warnings + tool versions
<project>/kb/<doc>/assets/         images, table renders
```

## CLI surface (planned)

```
kb extract <path> [--force] [--dry-run] [--json] [--only ext[,ext]] [--adapter name]
kb verify <path>  [--json] [--fail-fast]
kb manifest <path> [--status ok|partial|failed|skipped] [--format table|json|csv]
kb adapters
kb --version
```

## Not in v1

LLM-assisted section refinement, OCR for scanned PDFs, STP CAD metadata, Visio,
cross-document wiki organization, user memory, GitHub auto-publish. Each is a
separate planned sub-project — see the design spec.
